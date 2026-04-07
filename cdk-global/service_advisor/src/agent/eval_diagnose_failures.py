"""Diagnose failing traces for the Service Advisor Agent.

Fetches the last N traces from MLflow, runs LLM judge scores against each
one, flags any that fail, then performs root-cause analysis and suggests
specific code fixes.

Usage:
    python eval_diagnose_failures.py
"""

import json
import os
import sys
import textwrap
from pathlib import Path

os.environ.setdefault("DATABRICKS_CONFIG_PROFILE", "group-demo")

import mlflow
from mlflow import MlflowClient
from mlflow.genai.judges import meets_guidelines
from databricks_langchain import ChatDatabricks
from langchain_core.messages import HumanMessage, SystemMessage

EXPERIMENT_ID = "4485335598906791"
N_TRACES = 5
AGENT_SOURCE_FILE = Path(__file__).parent / "agent.py"

# ---------------------------------------------------------------------------
# Judge definitions — tailored to this agent's behavior contracts
# ---------------------------------------------------------------------------
JUDGE_GUIDELINES = [
    {
        "name": "response_answers_query",
        "guideline": (
            "The response must directly address what the user asked. "
            "If the user asked for appointments the response must include appointment data. "
            "If the user asked about a customer the response must include customer details. "
            "If the user asked for revenue or analytics the response must include real numbers. "
            "A vague or off-topic response is a failure."
        ),
    },
    {
        "name": "no_refusal_or_generic_answer",
        "guideline": (
            "The response must NOT contain phrases like 'I don't have access', "
            "'I cannot answer', 'I don't have that information', or give a "
            "generic non-answer. The agent has tools and a Genie data space and "
            "must always provide real data. A response that describes what it "
            "could do without actually doing it is a failure."
        ),
    },
    {
        "name": "tool_output_present_for_data_query",
        "guideline": (
            "If the query asks for data (appointments, customer info, revenue, "
            "technician rankings, service history), the response must contain "
            "actual data values — names, numbers, dates, dollar amounts. "
            "A response that only narrates what the agent is about to do, or "
            "lists generic steps, without showing real results is a failure."
        ),
    },
]

# ---------------------------------------------------------------------------
# Agent architecture summary fed to the diagnosis LLM
# ---------------------------------------------------------------------------
_AGENT_ARCH_SUMMARY = """\
KEY AGENT NODES:
- router (_router): classifies intent into 7 branches using ROUTER_PROMPT;
  defaults to genie_query when unsure.
- daily_briefing: deterministic pipeline —
  fetch_appointments → fetch_top_clv → fetch_best_tech → present_briefing
- genie_query (_genie_query): must call query_genie tool; governed by
  GENIE_QUERY_PROMPT which says "NEVER say you cannot answer".
- general_agent (_general_agent): ReAct loop with all tools; must never
  refuse — fall back to query_genie if specific tools fail.
- customer_lookup (_customer_lookup): uses get_customer_profile or query_genie.
- handle_assign (_handle_assign): assigns technician; uses all_tools.
- check_assignment (_check_assignment): checks assignment status.

TOOLS AVAILABLE:
- get_todays_appointments, get_customer_profile, get_highest_clv_customer,
  get_best_technician, get_technician_schedule  (UC Functions)
- assign_technician, get_assignment_status  (assignment_tools)
- query_genie  (genie_tools) — answers ANY natural-language dealership query

COMMON FAILURE PATTERNS IN THIS ARCHITECTURE:
1. Router misclassifies → wrong branch → no tool call → empty/wrong response.
2. genie_query node skips tool call → LLM hallucinates instead of calling query_genie.
3. present_briefing calls LLM without enough context → vague summary.
4. general_agent falls through without calling any tool for a data question.
5. Tool returns an error string → agent presents the error as the answer.
"""


# ---------------------------------------------------------------------------
# MLflow helpers
# ---------------------------------------------------------------------------

def _setup():
    # The group-demo profile uses OAuth (auth_type = databricks-cli), not a PAT.
    # MLflow can't follow OAuth on its own, so we use the SDK to fetch a live
    # bearer token and inject it as DATABRICKS_TOKEN before MLflow connects.
    from databricks.sdk import WorkspaceClient

    profile = os.environ.get("DATABRICKS_CONFIG_PROFILE", "group-demo")
    w = WorkspaceClient(profile=profile)
    headers = w.config.authenticate()
    token = headers.get("Authorization", "").removeprefix("Bearer ").strip()

    os.environ["DATABRICKS_HOST"] = w.config.host.rstrip("/")
    os.environ["DATABRICKS_TOKEN"] = token

    mlflow.set_tracking_uri("databricks")
    mlflow.set_experiment(experiment_id=EXPERIMENT_ID)


def _fetch_traces(n: int) -> list:
    client = MlflowClient()
    return list(
        client.search_traces(
            locations=[EXPERIMENT_ID],
            max_results=n,
            order_by=["timestamp_ms DESC"],
        )
    )


def _extract_io(trace) -> tuple[str, str]:
    """Return (user_query, agent_response) from a trace's root span."""
    spans = trace.data.spans or []
    root = next((s for s in spans if not s.parent_id), None)
    if not root:
        return "", ""

    # ---- query -----------------------------------------------------------
    query = ""
    try:
        inp = root.inputs or {}
        if isinstance(inp, str):
            inp = json.loads(inp)
        messages = inp.get("messages", [])
        query = next(
            (m.get("content", "") for m in messages if m.get("role") == "user"),
            str(inp)[:500],
        )
    except Exception:
        pass

    # ---- response --------------------------------------------------------
    response = ""
    try:
        out = root.outputs or {}
        if isinstance(out, str):
            out = json.loads(out)
        for item in reversed(out.get("output", [])):
            if isinstance(item, dict) and item.get("role") == "assistant":
                for part in item.get("content", []):
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        txt = part.get("text", "")
                        if txt and not txt.startswith("[Step"):
                            response = txt
                            break
            if response:
                break
        if not response:
            response = str(out)[:600]
    except Exception:
        pass

    return query, response


def _build_span_tree(trace) -> str:
    """Return a compact, readable span tree for the diagnosis LLM."""
    spans = trace.data.spans or []
    if not spans:
        return "(no spans)"

    children: dict[str, list] = {}
    for s in spans:
        pid = s.parent_id
        if pid:
            children.setdefault(pid, []).append(s)

    lines: list[str] = []

    def _fmt(span, depth: int = 0):
        indent = "  " * depth
        try:
            code = span.status.status_code
            err_flag = " ⚠️ ERROR" if str(code).upper() in {"ERROR", "STATUS_CODE_ERROR"} else ""
        except Exception:
            err_flag = ""

        out_str = ""
        try:
            outs = span.outputs
            if outs and outs not in ({}, "{}"):
                out_str = (
                    json.dumps(outs)[:300]
                    if not isinstance(outs, str)
                    else outs[:300]
                )
        except Exception:
            pass

        lines.append(f"{indent}[{span.name}]{err_flag}")
        if out_str:
            lines.append(f"{indent}  → {out_str}")

        for child in children.get(span.span_id, []):
            _fmt(child, depth + 1)

    roots = [s for s in spans if not s.parent_id]
    for root in roots:
        _fmt(root)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Judging
# ---------------------------------------------------------------------------

def _run_judges(query: str, response: str) -> list[dict]:
    """Score one trace against all JUDGE_GUIDELINES. Returns list of result dicts."""
    results = []
    for jd in JUDGE_GUIDELINES:
        try:
            fb = meets_guidelines(
                name=jd["name"],
                guidelines=jd["guideline"],
                context={"request": query, "response": response},
            )
            value = getattr(fb, "value", None)
            passed = str(value).lower() in {"yes", "true", "1"}
            results.append({
                "name": jd["name"],
                "value": value,
                "rationale": getattr(fb, "rationale", ""),
                "passed": passed,
            })
        except Exception as exc:
            results.append({
                "name": jd["name"],
                "value": "error",
                "rationale": str(exc),
                "passed": False,
            })
    return results


# ---------------------------------------------------------------------------
# Root-cause diagnosis
# ---------------------------------------------------------------------------

def _diagnose(trace, query: str, response: str, failing: list[dict], source: str, llm) -> dict:
    """Ask an LLM to root-cause the failure and suggest a specific code fix."""
    span_tree = _build_span_tree(trace)
    failing_text = "\n".join(
        f"  • {j['name']}: {j['value']}\n    Reason: {j['rationale']}"
        for j in failing
    )

    prompt = f"""You are debugging a LangGraph Service Advisor Agent (agent.py) for a CDK car dealership.

## USER QUERY
{query}

## AGENT RESPONSE
{response[:700]}

## FAILING QUALITY CHECKS
{failing_text}

## WHAT THE AGENT DID (span execution tree)
```
{span_tree[:2500]}
```

## AGENT ARCHITECTURE REFERENCE
{_AGENT_ARCH_SUMMARY}

## AGENT SOURCE CODE (agent.py)
```python
{source[:7000]}
```

## YOUR TASK
Based on the failing checks and span tree, identify the root cause and a concrete fix.

Return ONLY a valid JSON object — no markdown fences, no prose outside the JSON:
{{
  "root_cause_node": "<exact function or constant name, e.g. _router, GENIE_QUERY_PROMPT>",
  "failure_explanation": "<2-3 sentences: what specifically went wrong, which branch was taken, why the output was bad>",
  "code_fix": {{
    "function": "<exact function/constant to edit>",
    "change_description": "<one sentence>",
    "before": "<quote the exact current code lines>",
    "after": "<the replacement lines>"
  }},
  "priority": "HIGH|MEDIUM|LOW"
}}"""

    raw = llm.invoke([
        SystemMessage(content="Expert AI agent debugger. Return valid JSON only, no markdown."),
        HumanMessage(content=prompt),
    ]).content.strip()

    # Strip accidental code fences
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                raw = part
                break

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "root_cause_node": "parse_error",
            "failure_explanation": raw[:400],
            "code_fix": {
                "function": "unknown",
                "change_description": "See failure_explanation above.",
                "before": "",
                "after": "",
            },
            "priority": "MEDIUM",
        }


# ---------------------------------------------------------------------------
# Report printing
# ---------------------------------------------------------------------------

def _print_report(scored: list[dict]) -> None:
    failing = [t for t in scored if not t["all_passed"]]

    print("\n" + "=" * 72)
    print("  SERVICE ADVISOR AGENT — FAILURE DIAGNOSIS REPORT")
    print("=" * 72)
    print(f"\n  Traces evaluated : {len(scored)}")
    print(f"  Passing          : {len(scored) - len(failing)}")
    print(f"  Failing          : {len(failing)}")

    if not failing:
        print("\n  ✅ All traces passed every quality check. No fixes needed.\n")
        print("=" * 72 + "\n")
        return

    for i, t in enumerate(failing, 1):
        dx = t.get("diagnosis") or {}
        priority = dx.get("priority", "?")
        emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "⚪")

        print(f"\n{'─' * 72}")
        print(f"  {emoji}  Failing Trace {i}/{len(failing)}  [{priority} priority]")
        print(f"  Trace ID : {t['trace_id']}")
        print(f"  Query    : {t['query'][:80]}")
        print(f"{'─' * 72}")

        print("\n  📋 JUDGE SCORES:")
        for j in t["judge_results"]:
            icon = "✅" if j["passed"] else "❌"
            print(f"  {icon} {j['name']}: {j['value']}")
            if not j["passed"] and j["rationale"]:
                for line in textwrap.wrap(j["rationale"], 64):
                    print(f"      {line}")

        if dx:
            print(f"\n  🎯 ROOT CAUSE NODE: {dx.get('root_cause_node', 'unknown')}")

            print("\n  💡 WHY IT FAILED:")
            for line in textwrap.wrap(dx.get("failure_explanation", ""), 68):
                print(f"     {line}")

            fix = dx.get("code_fix", {})
            if fix and fix.get("function"):
                print(f"\n  🔧 CODE FIX → {fix['function']}")
                print(f"     {fix.get('change_description', '')}")
                before = fix.get("before", "").strip()
                after = fix.get("after", "").strip()
                if before:
                    print("\n     BEFORE:")
                    for line in before.split("\n"):
                        print(f"       {line}")
                if after:
                    print("\n     AFTER:")
                    for line in after.split("\n"):
                        print(f"       {line}")

    print(f"\n{'=' * 72}")
    print("  END OF REPORT")
    print("=" * 72 + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_failure_diagnosis():
    _setup()

    agent_source = ""
    try:
        agent_source = AGENT_SOURCE_FILE.read_text()
    except Exception:
        print("Warning: could not load agent.py — diagnosis will be less precise.")

    llm = ChatDatabricks(endpoint="databricks-claude-sonnet-4")

    print(f"\nFetching last {N_TRACES} traces from experiment {EXPERIMENT_ID}...")
    traces = _fetch_traces(N_TRACES)

    if not traces:
        print("No traces found. Run eval_llm_comparison.py first to generate traces.")
        return

    print(f"Found {len(traces)} trace(s). Running quality judges...\n")

    scored: list[dict] = []
    for trace in traces:
        trace_id = trace.info.trace_id
        print(f"  [{trace_id[:20]}...]", end=" ", flush=True)

        query, response = _extract_io(trace)
        if not query or not response:
            print("skipped — could not extract query/response from root span.")
            continue

        judge_results = _run_judges(query, response)
        all_passed = all(j["passed"] for j in judge_results)
        failing_judges = [j for j in judge_results if not j["passed"]]

        status = "✅ PASS" if all_passed else f"❌ FAIL ({len(failing_judges)} check(s) failed)"
        print(status)

        record: dict = {
            "trace_id": trace_id,
            "query": query,
            "response": response,
            "judge_results": judge_results,
            "all_passed": all_passed,
            "diagnosis": None,
        }

        if not all_passed:
            print("    → Diagnosing root cause...", end=" ", flush=True)
            record["diagnosis"] = _diagnose(
                trace, query, response, failing_judges, agent_source, llm
            )
            print("done")

        scored.append(record)

    _print_report(scored)


if __name__ == "__main__":
    run_failure_diagnosis()
