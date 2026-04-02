# Databricks notebook source
# MAGIC %md
# MAGIC # Tool Call Verification — Custom LLM Judge + Deterministic Scorers
# MAGIC
# MAGIC Evaluates the Parts Invoice Processing Agent using **MLflow 3 GenAI**:
# MAGIC
# MAGIC | Scorer | Type | What It Checks |
# MAGIC |--------|------|----------------|
# MAGIC | `tool_selection_accuracy` | Deterministic (`@scorer`) | Correct tools called via trace TOOL spans |
# MAGIC | `router_intent_accuracy` | Deterministic (`@scorer`) | Router classified the correct intent |
# MAGIC | `tool_call_judge` | LLM Judge (`make_judge`) | LLM reviews full trace for tool appropriateness |
# MAGIC
# MAGIC **Usage**: Run all cells top-to-bottom on a Databricks cluster. Results are logged
# MAGIC to the MLflow experiment and can be viewed in the Evaluation tab.

# COMMAND ----------

# MAGIC %pip install "mlflow[databricks]>=3.6.0" databricks-langchain langgraph==0.3.4 pydantic databricks-agents slack_sdk "psycopg[binary]>=3.0" "databricks-sdk>=0.68.0"
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./agent

# COMMAND ----------

import mlflow
import mlflow.genai
from mlflow.genai.scorers import scorer
from mlflow.genai.judges import make_judge
from mlflow.entities import Feedback, Trace, SpanType
from mlflow.types.responses import ResponsesAgentRequest, ChatContext

mlflow.set_tracking_uri(f"databricks://group-demo")
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment("/Workspace/Users/zach.jacobson@databricks.com/.bundle/parts_invoice_processing/dev/files/src/agent/log_model")
mlflow.langchain.autolog()
from agent import AGENT
# COMMAND ----------

# MAGIC %md
# MAGIC ## Evaluation Dataset
# MAGIC Each record maps a user query to the tools and router intent it should trigger.

# COMMAND ----------

eval_data = [
    # --- process_invoice: full pipeline (lookup → classify → match → submit) ---
    {
        "inputs": {"query": "Process invoice INV-001 for approval."},
        "expectations": {
            "expected_tools": ["get_invoice_details", "submit_for_approval"],
            "expected_intent": "process_invoice",
        },
    },
    {
        "inputs": {"query": "Review and submit INV-025 through the approval pipeline."},
        "expectations": {
            "expected_tools": ["get_invoice_details", "submit_for_approval"],
            "expected_intent": "process_invoice",
        },
    },

    # --- approve_invoice ---
    {
        "inputs": {"query": "I'm the Service Manager. Approve INV-001."},
        "expectations": {
            "expected_tools": ["approve_invoice"],
            "expected_intent": "approve_invoice",
        },
    },

    # --- reject_invoice ---
    {
        "inputs": {
            "query": "As Parts Director, reject INV-025 — the pricing doesn't match our contract rates."
        },
        "expectations": {
            "expected_tools": ["reject_invoice"],
            "expected_intent": "reject_invoice",
        },
    },

    # --- escalate_invoice ---
    {
        "inputs": {"query": "Escalate INV-010 to the next level."},
        "expectations": {
            "expected_tools": ["escalate_invoice"],
            "expected_intent": "escalate_invoice",
        },
    },

    # --- check_status ---
    {
        "inputs": {"query": "What's the approval status of INV-001?"},
        "expectations": {
            "expected_tools": ["get_approval_status"],
            "expected_intent": "check_status",
        },
    },

    # --- my_approvals ---
    {
        "inputs": {
            "query": "I'm the Service Manager — what invoices are pending my approval?"
        },
        "expectations": {
            "expected_tools": ["get_pending_approvals_for_route"],
            "expected_intent": "my_approvals",
        },
    },

    # --- general_query ---
    {
        "inputs": {"query": "Give me a summary of all invoices currently in the system."},
        "expectations": {
            "expected_tools": ["get_invoice_summary"],
            "expected_intent": "general_query",
        },
    },
    {
        "inputs": {"query": "How is AutoZone Commercial performing as a supplier?"},
        "expectations": {
            "expected_tools": ["get_supplier_performance"],
            "expected_intent": "general_query",
        },
    },
    {
        "inputs": {"query": "Show me all invoices routed to EXCEPTION_REVIEW."},
        "expectations": {
            "expected_tools": ["get_invoices_by_route"],
            "expected_intent": "general_query",
        },
    },
]

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scorer 1: Deterministic Tool Selection Accuracy
# MAGIC Inspects TOOL spans in the trace and compares against expected tools.

# COMMAND ----------

@scorer
def tool_selection_accuracy(inputs, outputs, expectations, trace):
    expected_tools = expectations.get("expected_tools", [])

    if not expected_tools:
        return Feedback(
            name="tool_selection_accuracy",
            value="skip",
            rationale="No expected_tools in expectations",
        )

    tool_spans = trace.search_spans(span_type=SpanType.TOOL)
    actual_tools = {span.name.split(".")[-1] for span in tool_spans}

    expected_normalized = {t.split(".")[-1] for t in expected_tools}

    missing = expected_normalized - actual_tools
    extra = actual_tools - expected_normalized
    all_expected_called = len(missing) == 0

    rationale_parts = [
        f"Expected: {sorted(expected_normalized)}",
        f"Actual: {sorted(actual_tools)}",
    ]
    if missing:
        rationale_parts.append(f"Missing: {sorted(missing)}")
    if extra:
        rationale_parts.append(f"Extra: {sorted(extra)}")

    return Feedback(
        name="tool_selection_accuracy",
        value="yes" if all_expected_called else "no",
        rationale=" | ".join(rationale_parts),
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scorer 2: Router Intent Accuracy
# MAGIC Checks if the router node classified the user's intent correctly by
# MAGIC inspecting the `intent` field written to agent state.

# COMMAND ----------

@scorer
def router_intent_accuracy(inputs, outputs, expectations, trace):
    expected_intent = expectations.get("expected_intent")

    if not expected_intent:
        return Feedback(
            name="router_intent_accuracy",
            value="skip",
            rationale="No expected_intent in expectations",
        )

    router_spans = [
        s for s in trace.search_spans()
        if "router" in s.name.lower()
    ]

    if not router_spans:
        return Feedback(
            name="router_intent_accuracy",
            value="no",
            rationale="No router span found in trace",
        )

    span_out = router_spans[0].outputs
    actual_intent = None

    if isinstance(span_out, dict):
        actual_intent = span_out.get("intent")
    elif isinstance(span_out, str):
        import json as _json
        try:
            parsed = _json.loads(span_out)
            actual_intent = parsed.get("intent")
        except (ValueError, AttributeError):
            pass

    if actual_intent is None:
        return Feedback(
            name="router_intent_accuracy",
            value="no",
            rationale=f"Could not extract intent from router span outputs: {str(span_out)[:200]}",
        )

    match = actual_intent == expected_intent
    return Feedback(
        name="router_intent_accuracy",
        value="yes" if match else "no",
        rationale=f"Expected '{expected_intent}', got '{actual_intent}'",
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Scorer 3: Custom LLM Judge — Tool Call Correctness
# MAGIC Uses `make_judge()` with `{{ trace }}` so the LLM can inspect the full
# MAGIC execution trace and judge whether the tools called were appropriate.

# COMMAND ----------

tool_call_judge = make_judge(
    name="tool_call_correctness",
    instructions="""You are evaluating an invoice processing agent for an auto dealership's parts department.

The agent handles these intents and should call the corresponding tools:
- process_invoice → get_invoice_details (lookup), then optionally get_supplier_performance, then submit_for_approval
- approve_invoice → approve_invoice
- reject_invoice → reject_invoice
- escalate_invoice → escalate_invoice
- check_status → get_approval_status
- my_approvals → get_pending_approvals_for_route
- general_query → one or more of: get_invoice_summary, get_supplier_performance, search_invoices_by_supplier, get_invoices_by_route, get_approval_summary

Given:
- The user's request: {{ inputs }}
- The agent's response: {{ outputs }}
- The full execution trace: {{ trace }}

Evaluate whether the agent called the CORRECT tools for the user's intent.
Consider:
1. Did the agent identify the right intent?
2. Were the right tools called for that intent?
3. Were the tool arguments reasonable (e.g. correct invoice ID passed)?
4. Were any unnecessary or wrong tools called?

Respond with exactly "yes" if the tool calls were appropriate, or "no" if they were not.
""",
    model="databricks:/databricks-meta-llama-3-3-70b-instruct",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## predict_fn Wrapper
# MAGIC Wraps the agent's `ResponsesAgent.predict()` so it matches the
# MAGIC `predict_fn(query=...)` signature that `mlflow.genai.evaluate()` expects.

# COMMAND ----------

def predict_fn(query):
    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": query}],
        context=ChatContext(user_id="zach.jacobson@databricks.com"),
    )
    response = AGENT.predict(request)

    output_parts = []
    for item in response.output:
        item_dict = item.model_dump(exclude_none=True)
        if item_dict.get("type") == "message":
            for block in item_dict.get("content", []):
                if block.get("text"):
                    output_parts.append(block["text"])

    return " ".join(output_parts) if output_parts else str(response.output)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Evaluation

# COMMAND ----------

results = mlflow.genai.evaluate(
    data=eval_data,
    predict_fn=predict_fn,
    scorers=[
        tool_selection_accuracy,
        router_intent_accuracy,
        tool_call_judge,
    ],
)

print("Evaluation complete!")
print(f"Run ID: {results.run_id}")
print(f"\nAggregate metrics:\n{results.metrics}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Results Summary

# COMMAND ----------

import pandas as pd

traces_df = mlflow.search_traces(run_id=results.run_id)

summary_cols = [
    col for col in traces_df.columns
    if any(
        s in col
        for s in [
            "tool_selection_accuracy",
            "router_intent_accuracy",
            "tool_call_correctness",
        ]
    )
]

if summary_cols:
    display(
        traces_df[["request", *summary_cols]]
        .rename(columns={"request": "query"})
    )
else:
    print("No scorer columns found — check trace feedback in the MLflow UI.")

# COMMAND ----------

pass_rates = {}
for col in summary_cols:
    if col in traces_df.columns:
        values = traces_df[col].dropna()
        yes_count = (values.astype(str).str.lower() == "yes").sum()
        pass_rates[col] = f"{yes_count}/{len(values)} ({100 * yes_count / len(values):.0f}%)"

print("Pass rates:")
for metric, rate in sorted(pass_rates.items()):
    print(f"  {metric}: {rate}")
