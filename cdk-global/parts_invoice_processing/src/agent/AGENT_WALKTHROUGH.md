# Parts Invoice Processing Agent — Component Walkthrough

A human-in-the-loop LangGraph agent that automates the invoice approval workflow for Sunset CDJR's parts department. Built on LangGraph + MLflow ResponsesAgent + Unity Catalog + Slack.

---

## High-Level Architecture

```
User Message
    │
    ▼
┌─────────┐
│  Router  │  ← LLM classifies intent + extracts invoice ID, role, reason
└────┬────┘
     │
     ├─ process_invoice ──► Lookup → Classify → Match Analysis → Submit for Approval
     ├─ approve_invoice ──► Approve Action → Slack Confirmation
     ├─ reject_invoice  ──► Reject Action → Slack Notification
     ├─ escalate_invoice ─► Escalate Action → Notify Next-Level Approver
     ├─ check_status ─────► Query Approval Log → Present Timeline
     ├─ my_approvals ─────► Query Pending by Role → Present Queue
     └─ general_query ────► ReAct Loop (any UC tool)
```

---

## 1. Imports and Module Setup (Lines 15–38)

```python
import approval_tools
import slack_notifier
```

The agent imports from three ecosystems:

| Source | What's Imported | Purpose |
|--------|----------------|---------|
| **MLflow** | `ResponsesAgent`, request/response types, streaming helpers | Serving interface — the agent is deployed as an MLflow model |
| **LangGraph** | `StateGraph`, `END`, `ToolNode`, `add_messages` | Graph execution engine — defines the workflow DAG |
| **LangChain** | `ChatDatabricks`, `UCFunctionToolkit`, message types | LLM access and Unity Catalog function tools |
| **Local modules** | `approval_tools`, `slack_notifier` | Custom write tools and Slack notifications |

`sys.path.insert(0, ...)` ensures the sibling modules (`approval_tools.py`, `slack_notifier.py`) are importable whether the code is running as a Databricks notebook or as a served MLflow model.

---

## 2. Configuration (Lines 47–49)

```python
LLM_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
CATALOG = os.environ.get("CATALOG", "home_zach_jacobson")
SCHEMA = os.environ.get("SCHEMA", "cdk")
```

- **LLM_ENDPOINT** — The Databricks Foundation Model serving endpoint used for all LLM calls (routing, classification, analysis, response generation).
- **CATALOG / SCHEMA** — Unity Catalog coordinates for all tables and functions. Configurable via environment variables so the same code works across dev/prod.

---

## 3. Prompts (Lines 58–172)

Each step in the workflow has a dedicated system prompt. This separates concerns — the LLM gets narrow, step-specific instructions rather than one monolithic prompt.

| Prompt | Used By | Purpose |
|--------|---------|---------|
| `ROUTER_PROMPT` | `_router` | Classifies user intent into one of 7 categories and extracts structured fields (invoice_id, role, reason) |
| `CLASSIFY_PROMPT` | `_classify` | Categorizes the invoice as STANDARD, DISCREPANCY, UNMATCHED, RECEIVING_ISSUE, or URGENT |
| `MATCH_ANALYSIS_PROMPT` | `_analyze_match` | Performs the 3-way match analysis (Invoice vs PO vs Receiving Report) |
| `SUBMIT_PROMPT` | `_submit_for_approval` | Instructs the LLM to call the `submit_for_approval` tool — this is the action step |
| `APPROVE_PROMPT` | `_handle_approve` | Instructs the LLM to call the `approve_invoice` tool |
| `REJECT_PROMPT` | `_handle_reject` | Instructs the LLM to call the `reject_invoice` tool with the reason |
| `ESCALATE_PROMPT` | `_handle_escalate` | Instructs the LLM to call the `escalate_invoice` tool |
| `MY_APPROVALS_PROMPT` | `_my_approvals` | Maps the user's role to an approval route and queries pending items |
| `GENERAL_QUERY_PROMPT` | `_general_agent` | Open-ended assistant for non-workflow questions |

---

## 4. Agent State (Lines 181–190)

```python
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
```

LangGraph passes this state dict between every node. Each node reads what it needs and writes its outputs back. The `messages` field uses `add_messages` which appends rather than replaces, building up a conversation history as the invoice moves through the pipeline.

| Field | Set By | Used By |
|-------|--------|---------|
| `messages` | Every node | Every node — conversation history |
| `intent` | Router | Conditional edges (graph routing) |
| `invoice_id` | Router | Lookup, approve, reject, escalate, status |
| `invoice_data` | Lookup | Classify, match analysis, submit |
| `supplier_data` | Lookup | Match analysis |
| `classification` | Classify | Match analysis, submit |
| `match_analysis` | Analyze Match | Submit |
| `rejection_reason` | Router | Reject handler |
| `user_role` | Router | Approve, reject, escalate, my_approvals |

---

## 5. Tool Initialization (Lines 196–219)

```python
class InvoiceProcessingAgent(ResponsesAgent):
    def __init__(self):
        ...
        self.uc_tools = uc_toolkit.tools        # 8 UC SQL functions (read-only)
        self.approval_tools = [...]              # 4 Python tools (write operations)
        self.all_tools = self.uc_tools + self.approval_tools
```

Two categories of tools:

**UC Functions (read-only, SQL-based):**

| Tool | Purpose |
|------|---------|
| `get_invoice_details` | Look up a single invoice with full match data |
| `search_invoices_by_supplier` | Find invoices by vendor name |
| `get_invoices_by_route` | List invoices assigned to an approval route |
| `get_supplier_performance` | Aggregated vendor metrics (match rate, value, variance) |
| `get_invoice_summary` | High-level processing summary grouped by status/route |
| `get_approval_status` | Full approval history for a specific invoice |
| `get_pending_approvals_for_route` | Pending items for a given approver role |
| `get_approval_summary` | Aggregate approval pipeline statistics |

**Approval Tools (write operations, Python-based):**

| Tool | Purpose |
|------|---------|
| `submit_for_approval` | INSERT into `invoice_approval_log` + send Slack notification |
| `approve_invoice` | UPDATE status to APPROVED + Slack confirmation |
| `reject_invoice` | UPDATE status to REJECTED + Slack notification |
| `escalate_invoice` | UPDATE + INSERT for escalation + Slack to next approver |

The approval tools use **Databricks Lakebase** (managed PostgreSQL) via `psycopg` for low-latency reads and writes. OAuth tokens are generated via the Databricks SDK and refreshed automatically every 50 minutes (before the 1-hour expiry).

---

## 6. Graph Nodes — Invoice Processing Pipeline

### 6a. Router (`_router`, Lines 224–249)

The entry point for every request. Sends the user's message to the LLM with `ROUTER_PROMPT` and parses the JSON response to extract:
- `intent` — which workflow branch to take
- `invoice_id` — the invoice being referenced
- `rejection_reason` — if rejecting, the reason
- `user_role` — the user's dealership role

Falls back to `general_query` if JSON parsing fails.

### 6b. Lookup (`_lookup_invoice`, Lines 254–297)

Deterministic (no LLM needed). Directly calls the `get_invoice_details` UC function with the extracted invoice ID. Then extracts the vendor name from the result and calls `get_supplier_performance` to fetch supplier context. Both are stored in state for downstream nodes.

### 6c. Classify (`_classify`, Lines 302–312)

LLM call with `CLASSIFY_PROMPT`. Given the raw invoice data, classifies into one of: STANDARD, DISCREPANCY, UNMATCHED, RECEIVING_ISSUE, URGENT. The classification text (with reasoning) is stored in state.

### 6d. Analyze Match (`_analyze_match`, Lines 317–331)

LLM call with `MATCH_ANALYSIS_PROMPT`. Performs the 3-way match analysis between Invoice, PO, and Receiving Report. Produces a structured analysis with a verdict (PASS/PARTIAL/FAIL) and risk flags.

### 6e. Submit for Approval (`_submit_for_approval`, Lines 336–353)

This is where the agent transitions from analysis to action. The LLM is given all accumulated context (invoice data, classification, match analysis) and bound to the `approval_tools`. The prompt explicitly instructs it to call `submit_for_approval` — this writes to the `invoice_approval_log` table and sends a Slack notification.

If the invoice qualifies for auto-approval (matched, under threshold, preferred vendor), it logs as AUTO_APPROVED and notifies AP. Otherwise, it logs as PENDING and notifies the appropriate approver channel.

---

## 7. Graph Nodes — Approval Actions

### 7a. Approve (`_handle_approve`, Lines 358–373)

When the router detects `approve_invoice` intent, this node runs. The LLM is bound to only the `approve_invoice` tool and prompted to execute the approval. The tool updates the approval log and sends Slack confirmation to the AP channel.

### 7b. Reject (`_handle_reject`, Lines 375–395)

Similar to approve, but includes the rejection reason extracted by the router. The tool updates the log with status REJECTED and the reason, then notifies AP via Slack.

### 7c. Escalate (`_handle_escalate`, Lines 397–412)

Escalates to the next level in the chain: SERVICE_MANAGER → PARTS_DIRECTOR → GENERAL_MANAGER. The tool marks the current entry as ESCALATED, creates a new PENDING entry for the next-level approver, and sends a Slack notification to the new approver's channel.

---

## 8. Graph Nodes — Query Paths

### 8a. Check Status (`_check_status`, Lines 417–431)

Queries the `invoice_approval_log` via the `get_approval_status` UC function and presents a timeline of all approval actions for the requested invoice.

### 8b. My Approvals (`_my_approvals`, Lines 436–450)

Maps the user's role (e.g., "Service Manager" → `SERVICE_MANAGER`) and queries `get_pending_approvals_for_route` to show their pending queue, sorted by wait time.

### 8c. General Agent (`_general_agent`, Lines 455–465)

A standard ReAct loop. The LLM has access to all tools (UC + approval) and can make multiple tool calls in a loop to answer open-ended questions about invoices, suppliers, or approval metrics.

---

## 9. Respond After Tool (`_respond_after_tool`, Lines 470–483)

A shared node used by all action branches (submit, approve, reject, escalate, status, my_approvals). After a tool executes, its raw output is in the message history. This node asks the LLM to summarize the result into a clean, user-facing response. It loops back to itself if the LLM decides to make additional tool calls.

---

## 10. Graph Construction (`_build_graph`, Lines 488–595)

Assembles the full LangGraph `StateGraph`. Key patterns:

**Conditional routing from the router:**
```
router → {intent} → appropriate branch
```

**Action branches follow a 3-node pattern:**
```
handler_node → tool_node → respond_node
```

Each action branch (submit, approve, reject, escalate) has:
1. A **handler node** — LLM decides which tool to call
2. A **tool node** — LangGraph's `ToolNode` executes the tool
3. A **respond node** — LLM summarizes the result for the user

The respond node can loop back through its own tool node if the LLM decides to make follow-up tool calls.

**General query uses a ReAct loop:**
```
general_agent ⇄ general_tools (loops until no more tool calls)
```

---

## 11. MLflow ResponsesAgent Interface (Lines 600–618)

```python
class InvoiceProcessingAgent(ResponsesAgent):
    def predict(self, request) -> ResponsesAgentResponse: ...
    def predict_stream(self, request) -> Generator[...]: ...
```

The agent implements MLflow's `ResponsesAgent` protocol, which is the interface for Databricks Model Serving. This enables:
- Deployment via `databricks.agents.deploy()`
- Testing via the AI Playground / Review App
- Streaming responses to the user as each graph node completes

`predict_stream` builds the graph, streams node updates, and yields response items as they're produced. `predict` collects all streamed items into a single response.

---

## 12. Model Registration (Lines 622–624)

```python
mlflow.langchain.autolog()
AGENT = InvoiceProcessingAgent()
mlflow.models.set_model(AGENT)
```

- `autolog()` — Automatically traces all LangChain/LangGraph calls to MLflow for observability.
- `set_model(AGENT)` — Registers the agent instance as the model to be logged by MLflow when `log_model.py` runs.

---

## Supporting Modules

### `approval_tools.py`

Four `@tool`-decorated functions that read/write `invoice_approval_log` in **Databricks Lakebase** (managed PostgreSQL) via `psycopg`. Uses parameterized queries for safety and a `_LakebaseConnection` singleton that handles OAuth token refresh on a background thread. Each tool also triggers the appropriate Slack notification via `slack_notifier`. Declared as a `DatabricksLakebase` resource in MLflow for automatic credential provisioning on the serving endpoint.

### `slack_notifier.py`

Sends structured Slack messages using Block Kit. Channel routing is configured via environment variables mapping approval routes to Slack channels (e.g., `SERVICE_MANAGER` → `#service-approvals`). Handles approval requests, confirmations, rejections, escalations, and auto-approval notices.

### UC Functions (`create_functions.sql`)

Eight SQL functions registered in Unity Catalog. Five query `gold_invoice_match` for invoice/supplier data. Three query `invoice_approval_log` for approval workflow state. All are read-only.

### Lakebase Setup (`03_create_approval_tables.py`)

Creates a Lakebase Provisioned instance (or reuses an existing one) and sets up the `invoice_approval_log` PostgreSQL table with proper indexes. This table is written to by the agent at runtime via psycopg for low-latency OLTP operations.

---

## Why an Agent Instead of a SQL Job?

A common question: "Could we do all of this with SQL logic inside a Databricks job?"

### What SQL CAN replace

The **deterministic data steps are already SQL.** The gold layer pipeline computes `match_status`, `approval_route`, `price_variance_pct`, and `quantity_variance` using rule-based SQL. The 8 UC functions are pure SQL queries. A SQL job could handle:

- **Lookup**: Direct `SELECT` from `gold_invoice_match`
- **Classification**: `CASE WHEN` rules instead of LLM calls — the logic is deterministic
- **Approval routing**: Already computed in the gold layer — no LLM needed
- **Batch submission**: `INSERT INTO invoice_approval_log SELECT ... FROM gold_invoice_match` to bulk-submit all invoices in one statement
- **LLM summaries from SQL**: Databricks `ai_query()` can call LLM endpoints directly from SQL for narrative analysis

### What SQL CANNOT replace

| Capability | SQL Job | Agent |
|-----------|---------|-------|
| **Conversational interface** | Runs on schedule/trigger — no user interaction | Responds to free-text like "process INV-042" or "what's in my queue?" |
| **Intent routing** | Fixed pipeline — same steps every run | LLM parses ambiguous input like "approve that AutoZone invoice" into structured actions |
| **Slack integration** | No mechanism to call external APIs | Sends rich Block Kit notifications, tracks threads, routes to channels by approval level |
| **Writing to Lakebase** | SQL tasks run against Spark/DBSQL, not PostgreSQL | Direct `psycopg` writes for sub-second OLTP operations |
| **Multi-turn conversation** | Fire-and-forget — no state across runs | Maintains conversation context: "approve INV-042" → "what else is pending?" |
| **Human-in-the-loop** | Cannot pause for human input | Waits for approver to approve, reject, or escalate before proceeding |

### The bottom line

A **SQL job** handles the **batch processing pipeline** — ingesting invoices, computing matches, classifying, and auto-routing into an approval queue. That's what the SDP pipeline already does.

The **agent** provides the **interactive layer on top** — where humans ask questions, take approval actions in natural language, and get real-time Slack notifications. If you didn't need the conversational interface, Slack integration, and human-in-the-loop approvals, the entire workflow could collapse into a single SQL pipeline with no Python or LLM calls.

---

## Real-World Session: A Day in the AP Department

Below is a realistic multi-turn conversation showing how the Sunset CDJR accounts payable team would interact with the agent throughout a workday. Each message maps to actual invoices from `gold_invoice_match`.

### Morning: Processing the overnight invoice batch

**AP Clerk (Maria):**

> "Give me a summary of Delphi Technologies and Motorcraft OEM Supply invoices and list out each invoice_ids,manufacturers, and status."

The agent calls `get_invoice_summary` and returns a breakdown: 17 matched/auto-approved, 8 needing service manager review, 5 exception reviews, 2 PO-required, and 11 receiving reviews.

**Maria:**

> "Process invoice INV-00106 for approval."

The agent runs the full 4-step pipeline: looks up **INV-00106** (invoice MOT-211090, a $3,994.89 order from **Motorcraft OEM Supply** for the Service department), classifies it as **STANDARD** (matched, no price or quantity variance), runs the 3-way match (PASS — quantities and prices align, receiving confirmed), and submits it for **SERVICE_MANAGER** approval. Slack notification goes to `#service-approvals`.

**Maria:**

> "Whats the approval route on INV-00150, that one had a quantity mismatch."
> "Change the routing to SERVICE_MANAGER"

The agent looks it up — **INV-00100** (invoice O'R-447704), a $1,634.88 order from **O'Reilly Auto Parts** for the Service department. Price variance is **9.19%** above the PO. Classifies it as **DISCREPANCY**, match analysis returns FAIL on price (PRICE_MISMATCH), and routes it to **EXCEPTION_REVIEW**. Slack goes to `#exception-review` with the variance details.

**Maria:**

> "SKIP."

The agent processes **INV-00113** (invoice MAH-883132), a $66.20 order from **Mahle Aftermarket** for the Service department. No PO reference found (**NO_PO_REFERENCE**). Classifies it as **UNMATCHED** and routes it to **PO_REQUIRED**. Slack notification goes to `#exception-review` so procurement can locate or create the PO.

### Mid-morning: Service Manager reviews the queue

**Service Manager (Dave):**

> "I am the service manager can you show me my assigned invoices."

The agent maps his role to `SERVICE_MANAGER`, calls `get_pending_approvals_for_route`, and presents his queue: INV-00106 (Motorcraft, $3,994.89), INV-00140 (Motorcraft, $1,761.09), INV-00165 (Gates Corporation, $2,608.86), INV-00141 (Standard Motor Products, $1,411.92), and others — totaling over $12,000 across 8 invoices.

**Dave:**

> "Approve INV-00106. Motorcraft OEM parts for the service bay look good."

The agent calls `approve_invoice`, updates the approval log to APPROVED, and sends a Slack confirmation to `#ap-invoices` so the AP team knows they can schedule payment for the $3,994.89.

**Dave:**

> "SKIP to below"

The agent looks up **INV-00150** (invoice DEL-221707) — a $2,289.07 order from **Delphi Technologies** for the Quick Lane department. It has a **QUANTITY_MISMATCH** (variance of 1 unit). Still PENDING in EXCEPTION_REVIEW.

**Dave:**

> "Escalate INV-00150 to the GM of parts. I want her to review the quantity discrepancy with the warehouse."

The agent calls `escalate_invoice`, marks Dave's entry as ESCALATED, creates a new PENDING entry for **PARTS_DIRECTOR**, and sends a Slack notification to `#parts-approvals` explaining the quantity mismatch escalation.

### Afternoon: Parts Director handles escalations

**Parts Director (Linda):**

> "I'm the Parts Director. Show me my pending approvals."

The agent shows 2 items: **INV-00150** (escalated from Dave — Delphi Technologies, $2,289.07, quantity mismatch of 1 unit in Quick Lane) and **INV-00117** (Mahle Aftermarket, $11,384.45, matched but over $5K threshold, Quick Lane department).

**Linda:**

> "Reject INV-00150. We only received 4 of 5 units — vendor needs to ship the remaining unit or issue a credit memo for the difference."

The agent calls `reject_invoice` with the reason, updates the log to REJECTED, and notifies AP via Slack with the rejection details and instructions to contact Delphi Technologies.

**Linda:**

> "SKIP"

Approved, logged, Slack confirmation sent to `#ap-invoices`.

### End of day: AP Clerk wraps up


**Maria:**

> "Check the status of INV-00150. Did the exception review team handle that Delphi quantity mismatch yet?"

The agent calls `get_approval_status` for INV-00150 — still PENDING in EXCEPTION_REVIEW. The 9.19% price variance on the $1,634.88 O'Reilly invoice hasn't been acted on yet.

**Maria:**

> "What invoices have changed in the past 8 hours?"

The agent calls `get_invoices_by_route` with route EXCEPTION_REVIEW — shows INV-00100 (O'Reilly, $1,634.88, price mismatch 9.19%), INV-00132 (Dayco Products, $1,297.00, price mismatch 10.39%), INV-00108 (Mahle Aftermarket, $326.43, price mismatch 14.59%), INV-00146 (Continental AG Parts, $265.64, quantity mismatch of 2), INV-00093 (Bosch Automotive, $145.06, quantity mismatch of 1), and INV-00127 (Continental AG Parts, $136.51, price mismatch 11.04%).

---

This session shows how the agent handles seven different intent types across three users and roles in a single workday — all mapped to actual invoices from `mfg_mc_se_sa.cdk.gold_invoice_match`. Each interaction builds on prior context and drives real actions in the approval system.
