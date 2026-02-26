"""
Parts Invoice Processing Agent - LangGraph + MLflow + Unity Catalog

Sequential multi-step workflow that enforces the dealership's business process:
  Router → Lookup → Classify → Match Analysis → Approval Routing → Respond

General queries (summaries, supplier search) use a flexible ReAct loop.
"""
import json
import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
    to_chat_completions_input,
)
from databricks_langchain import ChatDatabricks, UCFunctionToolkit
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from typing import Annotated, Generator, Sequence, TypedDict

# =============================================================================
# CONFIGURATION
# =============================================================================
LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
CATALOG = "home_zach_jacobson"
SCHEMA = "cdk"

# =============================================================================
# STEP-SPECIFIC PROMPTS
# =============================================================================
ROUTER_PROMPT = """You are an invoice processing intake router. Analyze the user's message and determine:

1. **intent**: Is this about a SPECIFIC invoice (process_invoice) or a general query (general_query)?
   - "process_invoice" if the user mentions an invoice number, invoice ID, or asks to process/review a specific invoice
   - "general_query" for summaries, supplier searches, approval queues, or general questions

2. **invoice_id**: If process_invoice, extract the invoice number or ID. Otherwise leave empty.

Respond with ONLY a JSON object, no other text:
{"intent": "process_invoice" or "general_query", "invoice_id": "the invoice number or empty string"}"""

CLASSIFY_PROMPT = """You are Step 2 of 4 in the invoice processing pipeline: CLASSIFICATION.

Given the invoice data below, classify this invoice into exactly one category:
- **STANDARD**: Invoice matches PO, quantities and prices align, routine processing
- **DISCREPANCY**: Invoice has price or quantity mismatches vs the PO
- **UNMATCHED**: Invoice has no PO reference or the PO was not found
- **RECEIVING_ISSUE**: Parts not yet received or only partially received
- **URGENT**: Any classification above, but the invoice is due within 3 days

Explain your classification reasoning in 2-3 sentences. Reference specific data points (match_status, price_variance_pct, quantity_variance, days_until_due).

Invoice data:
{invoice_data}"""

MATCH_ANALYSIS_PROMPT = """You are Step 3 of 4 in the invoice processing pipeline: 3-WAY MATCH ANALYSIS.

Analyze the three-way match between the Invoice, Purchase Order, and Receiving Report.

Previous classification: {classification}

Invoice data:
{invoice_data}

Supplier context:
{supplier_data}

Provide a structured analysis:
1. **Invoice vs PO**: Do quantities and prices match? Quantify any variance.
2. **PO vs Receiving Report**: Was the full order received? Any damage?
3. **Overall Match Verdict**: PASS, PARTIAL, or FAIL with specific reasons.
4. **Risk Flags**: Note anything unusual (high price variance, probationary vendor, pattern of discrepancies)."""

ROUTE_PROMPT = """You are Step 4 of 4 in the invoice processing pipeline: APPROVAL ROUTING & RECOMMENDATION.

Based on the complete analysis, provide the final processing recommendation.

Classification: {classification}
Match Analysis: {match_analysis}
Invoice Data: {invoice_data}

Provide:
1. **Approval Route**: Who needs to approve this and why (based on the approval_route field and business rules).
2. **Recommended Action**: What should the AP team do RIGHT NOW with this invoice.
3. **Next Steps**: Ordered list of concrete actions (e.g., "Contact supplier about price discrepancy", "Hold payment pending receiving confirmation").
4. **Priority Justification**: Why this priority level is appropriate given the due date and amount.

Business rules for reference:
- AUTO_APPROVED: Matched, under $1,000, preferred vendor OR matched and under $500
- SERVICE_MANAGER: Matched, $1,000-$5,000
- PARTS_DIRECTOR: Matched, $5,000-$15,000
- GENERAL_MANAGER: Matched, over $15,000
- EXCEPTION_REVIEW: Any price/quantity mismatch or missing PO
- RECEIVING_REVIEW: Partial receipt or not yet received"""

GENERAL_QUERY_PROMPT = """You are an invoice processing assistant for Sunset Chrysler Dodge Jeep Ram's parts department. You help the accounts payable team with general queries about invoices, suppliers, and approval queues.

Use dollar amounts formatted with commas (e.g., $1,234.56). Be concise but thorough. When presenting tabular data, format it clearly."""


# =============================================================================
# STATE - carries structured context between sequential steps
# =============================================================================
class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]
    intent: str
    invoice_id: str
    invoice_data: str
    supplier_data: str
    classification: str
    match_analysis: str


# =============================================================================
# AGENT
# =============================================================================
class InvoiceProcessingAgent(ResponsesAgent):

    def __init__(self):
        self.llm = ChatDatabricks(endpoint=LLM_ENDPOINT)

        uc_toolkit = UCFunctionToolkit(
            function_names=[
                f"{CATALOG}.{SCHEMA}.get_invoice_details",
                f"{CATALOG}.{SCHEMA}.search_invoices_by_supplier",
                f"{CATALOG}.{SCHEMA}.get_pending_approvals",
                f"{CATALOG}.{SCHEMA}.get_supplier_performance",
                f"{CATALOG}.{SCHEMA}.get_invoice_summary",
            ]
        )
        self.tools = uc_toolkit.tools
        self.tools_by_name = {t.name: t for t in self.tools}

    # ------------------------------------------------------------------
    # Step 1: ROUTER – determine intent and extract invoice ID
    # ------------------------------------------------------------------
    def _router(self, state: AgentState) -> dict:
        user_msg = ""
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage):
                user_msg = m.content
                break

        response = self.llm.invoke([
            SystemMessage(content=ROUTER_PROMPT),
            HumanMessage(content=user_msg),
        ])

        try:
            raw = response.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            parsed = json.loads(raw)
            intent = parsed.get("intent", "general_query")
            invoice_id = parsed.get("invoice_id", "")
        except (json.JSONDecodeError, IndexError):
            intent = "general_query"
            invoice_id = ""

        return {"intent": intent, "invoice_id": invoice_id}

    # ------------------------------------------------------------------
    # Step 2: LOOKUP – deterministic tool call, no LLM needed
    # ------------------------------------------------------------------
    def _lookup_invoice(self, state: AgentState) -> dict:
        invoice_id = state.get("invoice_id", "")
        tool = self.tools_by_name.get(
            f"{CATALOG}__{SCHEMA}__get_invoice_details",
            self.tools_by_name.get("get_invoice_details"),
        )
        if not tool:
            for t in self.tools:
                if "invoice_details" in t.name:
                    tool = t
                    break

        result = tool.invoke({"invoice_number_input": invoice_id})
        invoice_data = str(result)

        supplier_name = ""
        try:
            if isinstance(result, str):
                for line in result.split("\n"):
                    if "supplier_name" in line.lower():
                        supplier_name = line.split(":")[-1].strip().strip("',\"")
                        break
            elif isinstance(result, (list, dict)):
                if isinstance(result, list) and result:
                    supplier_name = result[0].get("supplier_name", "")
                elif isinstance(result, dict):
                    supplier_name = result.get("supplier_name", "")
        except Exception:
            pass

        supplier_data = ""
        if supplier_name:
            sup_tool = None
            for t in self.tools:
                if "supplier_performance" in t.name:
                    sup_tool = t
                    break
            if sup_tool:
                supplier_data = str(sup_tool.invoke({"supplier_name_input": supplier_name}))

        return {
            "invoice_data": invoice_data,
            "supplier_data": supplier_data,
            "messages": [AIMessage(content=f"[Step 1/4 - Lookup] Retrieved invoice {invoice_id} and supplier context.")],
        }

    # ------------------------------------------------------------------
    # Step 3: CLASSIFY – LLM classifies the invoice
    # ------------------------------------------------------------------
    def _classify(self, state: AgentState) -> dict:
        prompt = CLASSIFY_PROMPT.format(invoice_data=state.get("invoice_data", ""))
        response = self.llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Classify this invoice."),
        ])
        classification = response.content
        return {
            "classification": classification,
            "messages": [AIMessage(content=f"[Step 2/4 - Classification]\n{classification}")],
        }

    # ------------------------------------------------------------------
    # Step 4: ANALYZE MATCH – LLM analyzes the 3-way match
    # ------------------------------------------------------------------
    def _analyze_match(self, state: AgentState) -> dict:
        prompt = MATCH_ANALYSIS_PROMPT.format(
            invoice_data=state.get("invoice_data", ""),
            supplier_data=state.get("supplier_data", "No supplier data available."),
            classification=state.get("classification", ""),
        )
        response = self.llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Analyze the 3-way match."),
        ])
        match_analysis = response.content
        return {
            "match_analysis": match_analysis,
            "messages": [AIMessage(content=f"[Step 3/4 - Match Analysis]\n{match_analysis}")],
        }

    # ------------------------------------------------------------------
    # Step 5: ROUTE & RESPOND – final recommendation
    # ------------------------------------------------------------------
    def _route_and_respond(self, state: AgentState) -> dict:
        prompt = ROUTE_PROMPT.format(
            invoice_data=state.get("invoice_data", ""),
            classification=state.get("classification", ""),
            match_analysis=state.get("match_analysis", ""),
        )
        response = self.llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Provide the final approval routing and recommendation."),
        ])
        return {
            "messages": [AIMessage(content=f"[Step 4/4 - Routing & Recommendation]\n{response.content}")],
        }

    # ------------------------------------------------------------------
    # General query path – standard ReAct loop for non-invoice queries
    # ------------------------------------------------------------------
    def _general_agent(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.tools)
        msgs = [SystemMessage(content=GENERAL_QUERY_PROMPT)] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_general(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "general_tools"
        return "end"

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------
    def _build_graph(self):
        graph = StateGraph(AgentState)

        # Add all nodes
        graph.add_node("router", RunnableLambda(self._router))
        graph.add_node("lookup_invoice", RunnableLambda(self._lookup_invoice))
        graph.add_node("classify", RunnableLambda(self._classify))
        graph.add_node("analyze_match", RunnableLambda(self._analyze_match))
        graph.add_node("route_and_respond", RunnableLambda(self._route_and_respond))
        graph.add_node("general_agent", RunnableLambda(self._general_agent))
        graph.add_node("general_tools", ToolNode(self.tools))

        # Entry point
        graph.set_entry_point("router")

        # Router branches based on intent
        graph.add_conditional_edges(
            "router",
            lambda state: state.get("intent", "general_query"),
            {"process_invoice": "lookup_invoice", "general_query": "general_agent"},
        )

        # Sequential invoice processing pipeline
        graph.add_edge("lookup_invoice", "classify")
        graph.add_edge("classify", "analyze_match")
        graph.add_edge("analyze_match", "route_and_respond")
        graph.add_edge("route_and_respond", END)

        # General query ReAct loop
        graph.add_conditional_edges(
            "general_agent",
            self._should_continue_general,
            {"general_tools": "general_tools", "end": END},
        )
        graph.add_edge("general_tools", "general_agent")

        return graph.compile()

    # ------------------------------------------------------------------
    # ResponsesAgent interface
    # ------------------------------------------------------------------
    def predict(self, request: ResponsesAgentRequest) -> ResponsesAgentResponse:
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        return ResponsesAgentResponse(output=outputs)

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        messages = to_chat_completions_input([m.model_dump() for m in request.input])
        graph = self._build_graph()

        for event in graph.stream({"messages": messages}, stream_mode=["updates"]):
            if event[0] == "updates":
                for node_data in event[1].values():
                    if node_data.get("messages"):
                        yield from output_to_responses_items_stream(node_data["messages"])


mlflow.langchain.autolog()
AGENT = InvoiceProcessingAgent()
mlflow.models.set_model(AGENT)
