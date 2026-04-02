"""Compare different LLMs using the Service Advisor Agent.

Creates a separate MLflow GenAI app version per LLM endpoint, runs a
standard set of test queries through the agent, and logs traces + params
so you can compare quality, latency, and tool usage in the MLflow UI.

Usage:
    python eval_llm_comparison.py
"""

import os
import sys
import time

os.environ.setdefault("DATABRICKS_CONFIG_PROFILE", "group-demo")

import mlflow
from databricks.sdk import WorkspaceClient
from databricks_langchain import ChatDatabricks

EXPERIMENT_ID = "4485335598906791"

LLMS_TO_EVALUATE = [
    "databricks-meta-llama-3-3-70b-instruct",
    "databricks-claude-sonnet-4",
    "databricks-claude-opus-4-6",
]

TEST_QUERIES = [
    "Show me today's appointments.",
    "Who is the highest value customer today?",
    "What were total service revenues last month?",
    "Assign the best technician for the VIP customer's service.",
    "How many appointments have brake service scheduled this week?",
]


def run_evaluation():
    w = WorkspaceClient()
    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(experiment_id=EXPERIMENT_ID)

    sys.path.insert(0, os.path.dirname(__file__))

    import agent as agent_module

    for llm_endpoint in LLMS_TO_EVALUATE:
        print(f"\n{'='*60}")
        print(f"Evaluating: {llm_endpoint}")
        print(f"{'='*60}")

        model_name = f"service-advisor-{llm_endpoint}"
        mlflow.set_active_model(name=model_name)
        mlflow.log_model_params({
            "llm_endpoint": llm_endpoint,
            "agent_type": "ServiceAdvisorAgent",
            "num_test_queries": len(TEST_QUERIES),
        })

        agent_module.LLM_ENDPOINT = llm_endpoint
        try:
            agent = agent_module.ServiceAdvisorAgent()
            agent.llm = ChatDatabricks(endpoint=llm_endpoint)
        except Exception as e:
            print(f"  SKIP — could not init agent with {llm_endpoint}: {e}")
            continue

        for i, query in enumerate(TEST_QUERIES, 1):
            print(f"  [{i}/{len(TEST_QUERIES)}] {query}")
            try:
                _run_single_query(agent, query, llm_endpoint, i)
            except Exception as e:
                print(f"    ERROR: {e}")

    print("\nDone! View results in the MLflow experiment UI.")


@mlflow.trace
def _run_single_query(agent, query: str, llm_endpoint: str, query_idx: int):
    from mlflow.types.responses import ResponsesAgentRequest

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": query}]
    )

    start = time.time()
    response = agent.predict(request)
    elapsed = time.time() - start

    output_text = _extract_final_response(response)

    mlflow.log_model_params({
        f"query_{query_idx}_latency_s": round(elapsed, 2),
    })

    print(f"    {elapsed:.1f}s — {output_text[:100]}...")
    return output_text


def _extract_final_response(response) -> str:
    for item in reversed(response.output):
        d = item.model_dump()
        if d.get("role") == "assistant" and d.get("content"):
            for part in d["content"]:
                if part.get("type") == "output_text" and part.get("text"):
                    text = part["text"]
                    if not text.startswith("[Step"):
                        return text
    return "(no response)"


if __name__ == "__main__":
    run_evaluation()
