"""Service Advisor Agent — Daily Briefing & Technician Assignment.

LangGraph + MLflow + Unity Catalog + Lakebase

Workflow for CDK Global dealership service advisors:
  Router → Daily Briefing (appointments + top CLV + best tech) or General Query
  Advisors can assign technicians, look up customers, and check schedules.
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

os.environ.setdefault("DATABRICKS_CONFIG_PROFILE", "group-demo")

from databricks.sdk import WorkspaceClient
from databricks_langchain import ChatDatabricks, DatabricksFunctionClient, UCFunctionToolkit, set_uc_function_client
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

set_uc_function_client(DatabricksFunctionClient(client=WorkspaceClient()))
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt.tool_node import ToolNode
from typing import Annotated, Generator, Sequence, TypedDict

import assignment_tools  # noqa: E402
import genie_tools  # noqa: E402

# =============================================================================
# Configuration
# =============================================================================
LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
CATALOG = os.environ.get("CATALOG", "mfg_mc_se_sa")
SCHEMA = os.environ.get("SCHEMA", "cdk_service")

# =============================================================================
# Step-Specific Prompts
# =============================================================================
ROUTER_PROMPT = """You are a service advisor intake router for a CDK Global car dealership. Analyze the user's message and determine the intent.

Possible intents:
1. **daily_briefing** — User wants to see today's appointments, daily schedule, or morning briefing. Look for "today's appointments", "daily briefing", "what's on my schedule", "morning report", "who's coming in today".
2. **customer_lookup** — User asks about a specific customer by name or ID. Look for "tell me about customer", "customer profile", "CUST-".
3. **top_clv** — User wants to know the highest lifetime value customer today. Look for "top customer", "highest value", "VIP", "best customer", "most valuable".
4. **assign_technician** — User wants to assign a technician to an appointment. Look for "assign tech", "who should work on", "assign", "put [tech] on".
5. **check_assignment** — User wants to check if a tech has been assigned to an appointment.
6. **genie_query** — User wants to explore dealership data with natural language, ask analytics questions, view trends, or run ad-hoc queries. Look for "ask Genie", "query the data", "show me trends", "revenue breakdown", "data analysis", "how many", "what percentage", "compare", or any analytical/reporting question. **This is also the default for any question you are unsure about.**
7. **general_query** — ONLY for questions that are specifically about managing technician assignments or checking assignment status. For anything else, use genie_query.

Extract these fields:
- **intent**: One of the 7 intents above
- **customer_id**: Customer ID if mentioned, else empty string
- **appointment_id**: Appointment ID if mentioned, else empty string
- **service_type**: Service type if mentioned, else empty string

Respond with ONLY a JSON object, no other text:
{"intent": "...", "customer_id": "...", "appointment_id": "...", "service_type": "..."}"""

BRIEFING_SUMMARY_PROMPT = """You are a Service Advisor Assistant for a CDK Global car dealership. You have just retrieved today's appointments, identified the highest CLV customer, and found the best technician match.

Present a clear morning briefing to the service advisor:

1. **Today's Schedule** — Summarize all appointments in a clean table: time, customer name, vehicle, service type, CLV tier.
2. **VIP Customer Spotlight** — Highlight the highest-CLV customer with their details: name, vehicle, CLV score, total lifetime spend, visit count, and the service they need today.
3. **Recommended Technician** — Recommend the best-matched technician for the VIP customer's service. Explain why they're the best pick (score, specialization, CSAT, fix rate).
4. **Action** — Ask the advisor if they'd like to confirm the technician assignment.

Use dollar amounts formatted with commas. Be warm and professional — this is the advisor's start-of-day partner.

Appointments data:
{appointments}

Highest CLV customer:
{top_clv}

Best technician match:
{best_tech}"""

CUSTOMER_LOOKUP_PROMPT = """You are a Service Advisor Assistant. Present the customer profile in a clear, organized format.

Include:
- Contact info and preferred contact method
- Loyalty tier and tenure
- Vehicle details
- Lifetime value metrics (total spend, visits, CLV score)
- Any appointments scheduled

Customer data:
{customer_data}"""

ASSIGN_PROMPT = """You are assigning a technician to a customer's service appointment. Use the assign_technician tool to execute the assignment.

Appointment ID: {appointment_id}
Customer ID: {customer_id}
Technician ID: {tech_id}
Service type: {service_type}

After assigning, confirm the action and summarize who was assigned to what."""

GENIE_QUERY_PROMPT = """You are a Service Advisor Assistant with access to a Databricks Genie Space for data exploration. You MUST use the query_genie tool to answer the user's question. Do not respond without calling the tool first.

The Genie Space can answer any question about dealership data: service history, revenue, parts, technician performance, customer trends, appointments, and more.

After receiving the Genie response, present the results clearly:
- Format tabular data in a readable table
- Use dollar amounts with commas (e.g., $1,234.56)
- Highlight key insights
- If Genie returned SQL, you may mention it briefly for transparency

NEVER say you cannot answer or don't have the data. Always call query_genie."""

GENERAL_QUERY_PROMPT = """You are a Service Advisor Assistant for a CDK Global car dealership. You help service advisors with questions about appointments, customers, technicians, and assignments.

Use dollar amounts formatted with commas (e.g., $1,234.56). Be concise but thorough. When presenting tabular data, format it clearly.

You have access to tools for looking up appointments, customer profiles, CLV scores, technician rankings, and making assignments. You also have access to query_genie, which can answer any data question about the dealership by querying the database with natural language.

IMPORTANT: You must NEVER say you don't have information or can't answer a question. If none of the specific tools can answer the question, ALWAYS use the query_genie tool as a fallback. The Genie Space has access to all dealership data."""


# =============================================================================
# Agent State & Class Definition
# =============================================================================
class AgentState(TypedDict):
    messages: Annotated[Sequence, add_messages]
    intent: str
    customer_id: str
    appointment_id: str
    service_type: str
    appointments_data: str
    top_clv_data: str
    best_tech_data: str


class ServiceAdvisorAgent(ResponsesAgent):

    def __init__(self):
        self.llm = ChatDatabricks(endpoint=LLM_ENDPOINT)

        uc_toolkit = UCFunctionToolkit(
            function_names=[
                f"{CATALOG}.{SCHEMA}.get_todays_appointments",
                f"{CATALOG}.{SCHEMA}.get_customer_profile",
                f"{CATALOG}.{SCHEMA}.get_highest_clv_customer",
                f"{CATALOG}.{SCHEMA}.get_best_technician",
                f"{CATALOG}.{SCHEMA}.get_technician_schedule",
            ]
        )
        self.uc_tools = uc_toolkit.tools
        self.assignment_tools = [
            assignment_tools.assign_technician,
            assignment_tools.get_assignment_status,
        ]
        self.genie_tools = [genie_tools.query_genie]
        self.all_tools = self.uc_tools + self.assignment_tools + self.genie_tools
        self.tools_by_name = {t.name: t for t in self.all_tools}

    # ------------------------------------------------------------------
    # ROUTER
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
            "intent": parsed.get("intent", "genie_query"),
            "customer_id": parsed.get("customer_id", ""),
            "appointment_id": parsed.get("appointment_id", ""),
            "service_type": parsed.get("service_type", ""),
        }

    # ------------------------------------------------------------------
    # DAILY BRIEFING — 3-step deterministic pipeline
    # ------------------------------------------------------------------
    def _fetch_appointments(self, state: AgentState) -> dict:
        tool = None
        for t in self.uc_tools:
            if "todays_appointments" in t.name:
                tool = t
                break
        if not tool:
            return {
                "appointments_data": "ERROR: get_todays_appointments tool not found",
                "messages": [AIMessage(content="[Briefing] Could not find appointments tool.")],
            }

        result = str(tool.invoke({}))
        return {
            "appointments_data": result,
            "messages": [AIMessage(content="[Step 1/3 — Appointments] Retrieved today's schedule.")],
        }

    def _fetch_top_clv(self, state: AgentState) -> dict:
        tool = None
        for t in self.uc_tools:
            if "highest_clv" in t.name:
                tool = t
                break
        if not tool:
            return {
                "top_clv_data": "ERROR: get_highest_clv_customer tool not found",
                "messages": [AIMessage(content="[Briefing] Could not find CLV tool.")],
            }

        result = str(tool.invoke({}))

        service_type = ""
        try:
            if "service_type" in result:
                for line in result.split("\n"):
                    if "service_type" in line.lower():
                        service_type = line.split(":")[-1].strip().strip("',\"")
                        break
        except Exception:
            pass

        return {
            "top_clv_data": result,
            "service_type": service_type or state.get("service_type", ""),
            "messages": [AIMessage(content="[Step 2/3 — Top CLV] Identified highest-value customer.")],
        }

    def _fetch_best_tech(self, state: AgentState) -> dict:
        tool = None
        for t in self.uc_tools:
            if "best_technician" in t.name:
                tool = t
                break
        if not tool:
            return {
                "best_tech_data": "ERROR: get_best_technician tool not found",
                "messages": [AIMessage(content="[Briefing] Could not find technician tool.")],
            }

        service_type = state.get("service_type", "General Service")
        result = str(tool.invoke({"service_type_input": service_type}))
        return {
            "best_tech_data": result,
            "messages": [AIMessage(content=f"[Step 3/3 — Best Tech] Found top technician for {service_type}.")],
        }

    def _present_briefing(self, state: AgentState) -> dict:
        prompt = BRIEFING_SUMMARY_PROMPT.format(
            appointments=state.get("appointments_data", "No data"),
            top_clv=state.get("top_clv_data", "No data"),
            best_tech=state.get("best_tech_data", "No data"),
        )
        llm_with_tools = self.llm.bind_tools(self.assignment_tools)
        response = llm_with_tools.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Present the daily briefing."),
        ])
        return {"messages": [response]}

    def _should_continue_briefing(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "briefing_tools"
        return "end"

    # ------------------------------------------------------------------
    # CUSTOMER LOOKUP
    # ------------------------------------------------------------------
    def _customer_lookup(self, state: AgentState) -> dict:
        customer_id = state.get("customer_id", "")
        if customer_id:
            llm_with_tools = self.llm.bind_tools(self.uc_tools)
            msgs = [
                SystemMessage(content="You are looking up a customer profile. Use the get_customer_profile tool to retrieve their details, then present them clearly."),
                HumanMessage(content=f"Look up customer {customer_id}."),
            ]
        else:
            llm_with_tools = self.llm.bind_tools(self.uc_tools + self.genie_tools)
            msgs = [
                SystemMessage(content=(
                    "You are looking up a customer profile. The user asked about a customer by name, "
                    "not by ID. Use the query_genie tool to search for the customer by name. "
                    "For example: 'Show me the profile for customer named Tracy Miller'. "
                    "If you find a customer ID in the results, you can then use get_customer_profile "
                    "to get their full details."
                )),
            ] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_customer(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "customer_tools"
        return "end"

    # ------------------------------------------------------------------
    # TOP CLV (standalone, without full briefing)
    # ------------------------------------------------------------------
    def _top_clv_lookup(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.uc_tools)
        msgs = [
            SystemMessage(content="You are identifying the highest lifetime value customer from today's appointments. Use the get_highest_clv_customer tool. Present their profile prominently with CLV score, total spend, and visit history."),
        ] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_top_clv(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "top_clv_tools"
        return "end"

    # ------------------------------------------------------------------
    # ASSIGN TECHNICIAN
    # ------------------------------------------------------------------
    def _handle_assign(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.all_tools)
        msgs = [
            SystemMessage(content="You are assigning a technician to a service appointment. First, if you don't have the appointment details, look them up. Then find the best technician for the service type. Finally, use the assign_technician tool to make the assignment. Explain your reasoning."),
        ] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_assign(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "assign_tools"
        return "end"

    # ------------------------------------------------------------------
    # CHECK ASSIGNMENT
    # ------------------------------------------------------------------
    def _check_assignment(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.assignment_tools)
        appointment_id = state.get("appointment_id", "")
        msgs = [
            SystemMessage(content="Check if a technician has been assigned to this appointment using the get_assignment_status tool."),
            HumanMessage(content=f"Check assignment for {appointment_id}."),
        ]
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_check(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "check_tools"
        return "end"

    # ------------------------------------------------------------------
    # GENIE QUERY — Natural language data exploration
    # ------------------------------------------------------------------
    def _genie_query(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.genie_tools)
        msgs = [
            SystemMessage(content=GENIE_QUERY_PROMPT),
        ] + list(state["messages"])
        response = llm_with_tools.invoke(msgs)
        return {"messages": [response]}

    def _should_continue_genie(self, state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "genie_tools"
        return "end"

    # ------------------------------------------------------------------
    # GENERAL QUERY — ReAct loop
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
    # RESPOND AFTER TOOL
    # ------------------------------------------------------------------
    def _respond_after_tool(self, state: AgentState) -> dict:
        llm_with_tools = self.llm.bind_tools(self.all_tools)
        msgs = [
            SystemMessage(content=(
                "Summarize the tool result for the user. Be clear and concise. "
                "Confirm what action was taken. "
                "If the tool result is empty, incomplete, or indicates an error, "
                "use the query_genie tool to try answering the question from the "
                "dealership data. NEVER tell the user you cannot answer."
            )),
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

        # Daily briefing pipeline
        graph.add_node("fetch_appointments", RunnableLambda(self._fetch_appointments))
        graph.add_node("fetch_top_clv", RunnableLambda(self._fetch_top_clv))
        graph.add_node("fetch_best_tech", RunnableLambda(self._fetch_best_tech))
        graph.add_node("present_briefing", RunnableLambda(self._present_briefing))
        graph.add_node("briefing_tools", ToolNode(self.assignment_tools))
        graph.add_node("briefing_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("briefing_respond_tools", ToolNode(self.all_tools))

        # Customer lookup
        graph.add_node("customer_lookup", RunnableLambda(self._customer_lookup))
        graph.add_node("customer_tools", ToolNode(self.uc_tools + self.genie_tools))
        graph.add_node("customer_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("customer_respond_tools", ToolNode(self.all_tools))

        # Top CLV standalone
        graph.add_node("top_clv_lookup", RunnableLambda(self._top_clv_lookup))
        graph.add_node("top_clv_tools", ToolNode(self.uc_tools))
        graph.add_node("top_clv_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("top_clv_respond_tools", ToolNode(self.all_tools))

        # Assign technician
        graph.add_node("handle_assign", RunnableLambda(self._handle_assign))
        graph.add_node("assign_tools", ToolNode(self.all_tools))
        graph.add_node("assign_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("assign_respond_tools", ToolNode(self.all_tools))

        # Check assignment
        graph.add_node("check_assignment", RunnableLambda(self._check_assignment))
        graph.add_node("check_tools", ToolNode(self.assignment_tools))
        graph.add_node("check_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("check_respond_tools", ToolNode(self.all_tools))

        # Genie query
        graph.add_node("genie_query", RunnableLambda(self._genie_query))
        graph.add_node("genie_tools", ToolNode(self.genie_tools))
        graph.add_node("genie_respond", RunnableLambda(self._respond_after_tool))
        graph.add_node("genie_respond_tools", ToolNode(self.all_tools))

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
                "daily_briefing": "fetch_appointments",
                "customer_lookup": "customer_lookup",
                "top_clv": "top_clv_lookup",
                "assign_technician": "handle_assign",
                "check_assignment": "check_assignment",
                "genie_query": "genie_query",
                "general_query": "general_agent",
            },
        )

        # Daily briefing pipeline: Appointments → Top CLV → Best Tech → Present
        graph.add_edge("fetch_appointments", "fetch_top_clv")
        graph.add_edge("fetch_top_clv", "fetch_best_tech")
        graph.add_edge("fetch_best_tech", "present_briefing")
        graph.add_conditional_edges("present_briefing", self._should_continue_briefing, {"briefing_tools": "briefing_tools", "end": END})
        graph.add_edge("briefing_tools", "briefing_respond")
        graph.add_conditional_edges("briefing_respond", self._should_continue_respond, {"respond_tools": "briefing_respond_tools", "end": END})
        graph.add_edge("briefing_respond_tools", "briefing_respond")

        # Customer lookup flow
        graph.add_conditional_edges("customer_lookup", self._should_continue_customer, {"customer_tools": "customer_tools", "end": END})
        graph.add_edge("customer_tools", "customer_respond")
        graph.add_conditional_edges("customer_respond", self._should_continue_respond, {"respond_tools": "customer_respond_tools", "end": END})
        graph.add_edge("customer_respond_tools", "customer_respond")

        # Top CLV flow
        graph.add_conditional_edges("top_clv_lookup", self._should_continue_top_clv, {"top_clv_tools": "top_clv_tools", "end": END})
        graph.add_edge("top_clv_tools", "top_clv_respond")
        graph.add_conditional_edges("top_clv_respond", self._should_continue_respond, {"respond_tools": "top_clv_respond_tools", "end": END})
        graph.add_edge("top_clv_respond_tools", "top_clv_respond")

        # Assign technician flow
        graph.add_conditional_edges("handle_assign", self._should_continue_assign, {"assign_tools": "assign_tools", "end": END})
        graph.add_edge("assign_tools", "assign_respond")
        graph.add_conditional_edges("assign_respond", self._should_continue_respond, {"respond_tools": "assign_respond_tools", "end": END})
        graph.add_edge("assign_respond_tools", "assign_respond")

        # Check assignment flow
        graph.add_conditional_edges("check_assignment", self._should_continue_check, {"check_tools": "check_tools", "end": END})
        graph.add_edge("check_tools", "check_respond")
        graph.add_conditional_edges("check_respond", self._should_continue_respond, {"respond_tools": "check_respond_tools", "end": END})
        graph.add_edge("check_respond_tools", "check_respond")

        # Genie query flow
        graph.add_conditional_edges("genie_query", self._should_continue_genie, {"genie_tools": "genie_tools", "end": END})
        graph.add_edge("genie_tools", "genie_respond")
        graph.add_conditional_edges("genie_respond", self._should_continue_respond, {"respond_tools": "genie_respond_tools", "end": END})
        graph.add_edge("genie_respond_tools", "genie_respond")

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
AGENT = ServiceAdvisorAgent()
mlflow.models.set_model(AGENT)
