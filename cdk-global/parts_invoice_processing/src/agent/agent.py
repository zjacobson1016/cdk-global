"""Parts Invoice Processing Agent — Human-in-the-Loop Approval.

LangGraph + MLflow + Unity Catalog + Slack

Full approval workflow for Sunset CDJR's parts department:
  Router → Lookup → Classify → Match Analysis → Submit for Approval → Respond

Approvers can approve, reject, or escalate via agent chat or Slack.
General queries (summaries, supplier search) use a flexible ReAct loop.
"""
import json
import os
import sys

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
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from typing import Annotated, Generator, Sequence, TypedDict

import approval_tools  # noqa: E402
import slack_notifier  # noqa: E402

# =============================================================================
# Configuration
# =============================================================================
LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
CATALOG = os.environ.get("CATALOG", "mfg_mc_se_sa")
SCHEMA = os.environ.get("SCHEMA", "cdk")

# =============================================================================
# Step-Specific Prompts
# =============================================================================
ROUTER_PROMPT = """You are an invoice processing intake router for Sunset Chrysler Dodge Jeep Ram's parts department. Analyze the user's message and determine the intent.

Possible intents:
1. **process_invoice** — User wants to process/review a specific invoice through the approval pipeline. They mention an invoice number or ID.
2. **approve_invoice** — User wants to APPROVE an invoice. Look for phrases like "approve INV-042", "approved", "sign off on".
3. **reject_invoice** — User wants to REJECT an invoice. Look for "reject INV-042", "deny", "decline". There should be a reason.
4. **escalate_invoice** — User wants to ESCALATE an invoice to the next approval level. Look for "escalate INV-042", "bump up", "send to next level".
5. **check_status** — User wants to check the approval status of a specific invoice.
6. **my_approvals** — User asks what invoices are pending their approval. Look for "what do I need to approve", "my pending approvals", "what's in my queue".
7. **general_query** — Any other question (summaries, supplier searches, general reporting).

Extract these fields:
- **intent**: One of the 7 intents above
- **invoice_id**: Invoice number or ID if mentioned, else empty string
- **rejection_reason**: If rejecting, the reason given, else empty string
- **user_role**: If the user identifies their role (Service Manager, Parts Director, etc.), capture it, else empty string

Respond with ONLY a JSON object, no other text:
{"intent": "...", "invoice_id": "...", "rejection_reason": "...", "user_role": "..."}"""

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

SUBMIT_PROMPT = """You are Step 4 of 4 in the invoice processing pipeline: SUBMIT FOR APPROVAL.

Based on the complete analysis, you MUST now submit this invoice for approval using the submit_for_approval tool. This is not advisory — you are executing the approval workflow.

Classification: {classification}
Match Analysis: {match_analysis}
Invoice Data: {invoice_data}

The approval route has already been determined by the gold layer pipeline:
- Look for the `approval_route` field in the invoice data.
- Call the `submit_for_approval` tool with all required fields.

After submitting, provide a summary including:
1. Which approval route was selected and why (based on the business rules).
2. What the approver should look for when reviewing.
3. Any risk factors or things to note.

Business rules for reference:
- AUTO_APPROVED: Matched, under $1,000 for preferred vendor OR matched and under $500
- SERVICE_MANAGER: Matched, $1,000-$5,000
- PARTS_DIRECTOR: Matched, $5,000-$15,000
- GENERAL_MANAGER: Matched, over $15,000
- EXCEPTION_REVIEW: Any price/quantity mismatch or missing PO
- RECEIVING_REVIEW: Partial receipt or not yet received"""

APPROVE_PROMPT = """You are handling an invoice approval action. The user wants to approve invoice {invoice_id}.

Use the approve_invoice tool to execute the approval. The approved_by should be "{user_role}" (or "Approver" if no role was specified). Include any notes the user provided.

After approving, confirm the action and mention that the AP team has been notified."""

REJECT_PROMPT = """You are handling an invoice rejection. The user wants to reject invoice {invoice_id}.

Reason provided: {rejection_reason}

Use the reject_invoice tool to execute the rejection. The rejected_by should be "{user_role}" (or "Reviewer" if no role was specified).

After rejecting, confirm the action, restate the reason, and mention that the AP team has been notified."""

ESCALATE_PROMPT = """You are handling an invoice escalation. The user wants to escalate invoice {invoice_id} to the next approval level.

Use the escalate_invoice tool to execute the escalation. The escalated_by should be "{user_role}" (or "Approver" if no role was specified).

After escalating, explain which level it was escalated to and why, and confirm the new approver has been notified."""

MY_APPROVALS_PROMPT = """You are helping an approver check their pending invoice queue.

The user's role: {user_role}

Use the available tools to look up pending approvals. If the user specified their role, map it:
- "Service Manager" → route = "SERVICE_MANAGER"
- "Parts Director" → route = "PARTS_DIRECTOR"
- "General Manager" or "Dealer Principal" → route = "GENERAL_MANAGER"
- "Controller" or "AP Manager" → route = "EXCEPTION_REVIEW"
- Otherwise, search for "ALL" pending approvals

Present the results as a clear, prioritized list showing invoice ID, vendor, amount, match status, and how long each has been waiting."""

GENERAL_QUERY_PROMPT = """You are an invoice processing assistant for Sunset Chrysler Dodge Jeep Ram's parts department. You help the accounts payable team with general queries about invoices, suppliers, approval queues, and processing status.

Use dollar amounts formatted with commas (e.g., $1,234.56). Be concise but thorough. When presenting tabular data, format it clearly.

You have access to tools for looking up invoices, supplier performance, approval status, and processing summaries. Use them to answer the user's question."""


# =============================================================================
# Agent State & Class Definition
# =============================================================================
class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]
    intent: str
    invoice_id: str
    invoice_data: str
    supplier_data: str
    classification: str
    match_analysis: str
    rejection_reason: str
    user_role: str


class InvoiceProcessingAgent(ResponsesAgent):

    def __init__(self):
        self.llm = ChatDatabricks(endpoint=LLM_ENDPOINT)

        uc_toolkit = UCFunctionToolkit(
            function_names=[
                f"{CATALOG}.{SCHEMA}.get_invoice_details",
                f"{CATALOG}.{SCHEMA}.search_invoices_by_supplier",
                f"{CATALOG}.{SCHEMA}.get_invoices_by_route",
                f"{CATALOG}.{SCHEMA}.get_supplier_performance",
                f"{CATALOG}.{SCHEMA}.get_invoice_summary",
                f"{CATALOG}.{SCHEMA}.get_approval_status",
                f"{CATALOG}.{SCHEMA}.get_pending_approvals_for_route",
                f"{CATALOG}.{SCHEMA}.get_approval_summary",
            ]
        )
        self.uc_tools = uc_toolkit.tools
        self.approval_tools = [
            approval_tools.submit_for_approval,
            approval_tools.approve_invoice,
            approval_tools.reject_invoice,
            approval_tools.escalate_invoice,
        ]
        self.all_tools = self.uc_tools + self.approval_tools
        self.tools_by_name = {t.name: t for t in self.all_tools}

    # ------------------------------------------------------------------
    # ROUTER — determine intent and extract invoice ID / role / reason
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
        except (json.JSONDecodeError, IndexError):
            parsed = {}

        return {
            "intent": parsed.get("intent", "general_query"),
            "invoice_id": parsed.get("invoice_id", ""),
            "rejection_reason": parsed.get("rejection_reason", ""),
            "user_role": parsed.get("user_role", ""),
        }

    # ------------------------------------------------------------------
    # LOOKUP — deterministic tool call to fetch invoice + supplier data
    # ------------------------------------------------------------------
    def _lookup_invoice(self, state: AgentState) -> dict:
        invoice_id = state.get("invoice_id", "")

        tool = None
        for t in self.uc_tools:
            if "invoice_details" in t.name:
                tool = t
                break
        if not tool:
            return {
                "invoice_data": "ERROR: get_invoice_details tool not found",
                "messages": [AIMessage(content="[Lookup] Could not find invoice lookup tool.")],
            }

        result = tool.invoke({"invoice_number_input": invoice_id})
        invoice_data = str(result)

        supplier_name = ""
        try:
            if isinstance(result, str):
                for line in result.split("\n"):
                    if "vendor_name" in line.lower():
                        supplier_name = line.split(":")[-1].strip().strip("',\"")
                        break
            elif isinstance(result, (list, dict)):
                if isinstance(result, list) and result:
                    supplier_name = result[0].get("vendor_name", "")
                elif isinstance(result, dict):
                    supplier_name = result.get("vendor_name", "")
        except Exception:
            pass

        supplier_data = ""
        if supplier_name:
            for t in self.uc_tools:
                if "supplier_performance" in t.name:
                    supplier_data = str(t.invoke({"supplier_name_input": supplier_name}))
                    break

        return {
            "invoice_data": invoice_data,
            "supplier_data": supplier_data,
            "messages": [AIMessage(content=f"[Step 1/4 — Lookup] Retrieved invoice {invoice_id} and supplier context.")],
        }

    # ------------------------------------------------------------------
    # CLASSIFY — LLM classifies the invoice
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
            "messages": [AIMessage(content=f"[Step 2/4 — Classification]\n{classification}")],
        }

    # ------------------------------------------------------------------
    # ANALYZE MATCH — LLM analyzes the 3-way match
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
            "messages": [AIMessage(content=f"[Step 3/4 — Match Analysis]\n{match_analysis}")],
        }

    # ------------------------------------------------------------------
    # SUBMIT FOR APPROVAL — calls the approval tool, sends Slack notification
    # ------------------------------------------------------------------
    def _submit_for_approval(self, state: AgentState) -> dict:
        prompt = SUBMIT_PROMPT.format(
            invoice_data=state.get("invoice_data", ""),
            classification=state.get("classification", ""),
            match_analysis=state.get("match_analysis", ""),
        )
        llm_with_tools = self.llm.bind_tools(self.approval_tools)
        response = llm_with_tools.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Submit this invoice for approval now."),
        ])
        return {"messages": [response]}

    def _should_continue_submit(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "submit_tools"
        return "end"

    # ------------------------------------------------------------------
    # APPROVE / REJECT / ESCALATE — action nodes with tool calling
    # ------------------------------------------------------------------
    def _handle_approve(self, state: AgentState) -> dict:
        invoice_id = state.get("invoice_id", "")
        user_role = state.get("user_role", "Approver")
        prompt = APPROVE_PROMPT.format(invoice_id=invoice_id, user_role=user_role)
        llm_with_tools = self.llm.bind_tools([approval_tools.approve_invoice])
        response = llm_with_tools.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Approve invoice {invoice_id}."),
        ])
        return {"messages": [response]}

    def _should_continue_approve(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "approve_tools"
        return "end"

    def _handle_reject(self, state: AgentState) -> dict:
        invoice_id = state.get("invoice_id", "")
        user_role = state.get("user_role", "Reviewer")
        rejection_reason = state.get("rejection_reason", "No reason provided")
        prompt = REJECT_PROMPT.format(
            invoice_id=invoice_id,
            user_role=user_role,
            rejection_reason=rejection_reason,
        )
        llm_with_tools = self.llm.bind_tools([approval_tools.reject_invoice])
        response = llm_with_tools.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Reject invoice {invoice_id}. Reason: {rejection_reason}"),
        ])
        return {"messages": [response]}

    def _should_continue_reject(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "reject_tools"
        return "end"

    def _handle_escalate(self, state: AgentState) -> dict:
        invoice_id = state.get("invoice_id", "")
        user_role = state.get("user_role", "Approver")
        prompt = ESCALATE_PROMPT.format(invoice_id=invoice_id, user_role=user_role)
        llm_with_tools = self.llm.bind_tools([approval_tools.escalate_invoice])
        response = llm_with_tools.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Escalate invoice {invoice_id}."),
        ])
        return {"messages": [response]}

    def _should_continue_escalate(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "escalate_tools"
        return "end"

    # ------------------------------------------------------------------
    # CHECK STATUS — look up approval history for an invoice
    # ------------------------------------------------------------------
    def _check_status(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.uc_tools)
        invoice_id = state.get("invoice_id", "")
        msgs = [
            SystemMessage(content="You are checking the approval status of an invoice. Use the get_approval_status tool to look up the full history, then present a clear timeline."),
            HumanMessage(content=f"What is the approval status of {invoice_id}?"),
        ]
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_status(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "status_tools"
        return "end"

    # ------------------------------------------------------------------
    # MY APPROVALS — show pending approvals for a role
    # ------------------------------------------------------------------
    def _my_approvals(self, state: AgentState) -> dict:
        user_role = state.get("user_role", "")
        prompt = MY_APPROVALS_PROMPT.format(user_role=user_role or "unknown")
        llm_with_tools = self.llm.bind_tools(self.uc_tools)
        msgs = [
            SystemMessage(content=prompt),
        ] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_my_approvals(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "my_approvals_tools"
        return "end"

    # ------------------------------------------------------------------
    # GENERAL QUERY — standard ReAct loop for non-workflow queries
    # ------------------------------------------------------------------
    def _general_agent(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.all_tools)
        msgs = [SystemMessage(content=GENERAL_QUERY_PROMPT)] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_general(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "general_tools"
        return "end"

    # ------------------------------------------------------------------
    # RESPOND AFTER TOOL — LLM summarizes tool output for the user
    # ------------------------------------------------------------------
    def _respond_after_tool(self, state: AgentState) -> dict:
        """Generate a human-readable response after a tool has executed."""
        llm_with_tools = self.llm.bind_tools(self.all_tools)
        msgs = [
            SystemMessage(content="Summarize the tool result for the user. Be clear and concise. Confirm what action was taken."),
        ] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_respond(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "respond_tools"
        return "end"

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------
    def _build_graph(self):
        graph = StateGraph(AgentState)

        # Nodes
        graph.add_node("router", RunnableLambda(self._router))

        # Invoice processing pipeline
        graph.add_node("lookup_invoice", RunnableLambda(self._lookup_invoice))
        graph.add_node("classify", RunnableLambda(self._classify))
        graph.add_node("analyze_match", RunnableLambda(self._analyze_match))
        graph.add_node("submit_for_approval", RunnableLambda(self._submit_for_approval))
        graph.add_node("submit_tools", ToolNode(self.approval_tools))
        graph.add_node("submit_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("submit_respond_tools", ToolNode(self.all_tools))

        # Approval action nodes
        graph.add_node("handle_approve", RunnableLambda(self._handle_approve))
        graph.add_node("approve_tools", ToolNode([approval_tools.approve_invoice]))
        graph.add_node("approve_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("approve_respond_tools", ToolNode(self.all_tools))

        graph.add_node("handle_reject", RunnableLambda(self._handle_reject))
        graph.add_node("reject_tools", ToolNode([approval_tools.reject_invoice]))
        graph.add_node("reject_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("reject_respond_tools", ToolNode(self.all_tools))

        graph.add_node("handle_escalate", RunnableLambda(self._handle_escalate))
        graph.add_node("escalate_tools", ToolNode([approval_tools.escalate_invoice]))
        graph.add_node("escalate_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("escalate_respond_tools", ToolNode(self.all_tools))

        # Status & approvals query nodes
        graph.add_node("check_status", RunnableLambda(self._check_status))
        graph.add_node("status_tools", ToolNode(self.uc_tools))
        graph.add_node("status_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("status_respond_tools", ToolNode(self.all_tools))

        graph.add_node("my_approvals", RunnableLambda(self._my_approvals))
        graph.add_node("my_approvals_tools", ToolNode(self.uc_tools))
        graph.add_node("my_approvals_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("my_approvals_respond_tools", ToolNode(self.all_tools))

        # General query
        graph.add_node("general_agent", RunnableLambda(self._general_agent))
        graph.add_node("general_tools", ToolNode(self.all_tools))

        # Entry point
        graph.set_entry_point("router")

        # Router → intent branches
        graph.add_conditional_edges(
            "router",
            lambda state: state.get("intent", "general_query"),
            {
                "process_invoice": "lookup_invoice",
                "approve_invoice": "handle_approve",
                "reject_invoice": "handle_reject",
                "escalate_invoice": "handle_escalate",
                "check_status": "check_status",
                "my_approvals": "my_approvals",
                "general_query": "general_agent",
            },
        )

        # Invoice processing pipeline: Lookup → Classify → Match → Submit
        graph.add_edge("lookup_invoice", "classify")
        graph.add_edge("classify", "analyze_match")
        graph.add_edge("analyze_match", "submit_for_approval")
        graph.add_conditional_edges("submit_for_approval", self._should_continue_submit, {"submit_tools": "submit_tools", "end": END})
        graph.add_edge("submit_tools", "submit_respond")
        graph.add_conditional_edges("submit_respond", self._should_continue_respond, {"respond_tools": "submit_respond_tools", "end": END})
        graph.add_edge("submit_respond_tools", "submit_respond")

        # Approve flow
        graph.add_conditional_edges("handle_approve", self._should_continue_approve, {"approve_tools": "approve_tools", "end": END})
        graph.add_edge("approve_tools", "approve_respond")
        graph.add_conditional_edges("approve_respond", self._should_continue_respond, {"respond_tools": "approve_respond_tools", "end": END})
        graph.add_edge("approve_respond_tools", "approve_respond")

        # Reject flow
        graph.add_conditional_edges("handle_reject", self._should_continue_reject, {"reject_tools": "reject_tools", "end": END})
        graph.add_edge("reject_tools", "reject_respond")
        graph.add_conditional_edges("reject_respond", self._should_continue_respond, {"respond_tools": "reject_respond_tools", "end": END})
        graph.add_edge("reject_respond_tools", "reject_respond")

        # Escalate flow
        graph.add_conditional_edges("handle_escalate", self._should_continue_escalate, {"escalate_tools": "escalate_tools", "end": END})
        graph.add_edge("escalate_tools", "escalate_respond")
        graph.add_conditional_edges("escalate_respond", self._should_continue_respond, {"respond_tools": "escalate_respond_tools", "end": END})
        graph.add_edge("escalate_respond_tools", "escalate_respond")

        # Check status flow
        graph.add_conditional_edges("check_status", self._should_continue_status, {"status_tools": "status_tools", "end": END})
        graph.add_edge("status_tools", "status_respond")
        graph.add_conditional_edges("status_respond", self._should_continue_respond, {"respond_tools": "status_respond_tools", "end": END})
        graph.add_edge("status_respond_tools", "status_respond")

        # My approvals flow
        graph.add_conditional_edges("my_approvals", self._should_continue_my_approvals, {"my_approvals_tools": "my_approvals_tools", "end": END})
        graph.add_edge("my_approvals_tools", "my_approvals_respond")
        graph.add_conditional_edges("my_approvals_respond", self._should_continue_respond, {"respond_tools": "my_approvals_respond_tools", "end": END})
        graph.add_edge("my_approvals_respond_tools", "my_approvals_respond")

        # General query ReAct loop
        graph.add_conditional_edges("general_agent", self._should_continue_general, {"general_tools": "general_tools", "end": END})
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
