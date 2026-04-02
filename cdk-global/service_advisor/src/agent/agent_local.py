"""Test the Service Advisor Agent locally against a set of queries.

Usage:
    python agent_local.py
"""

import os

os.environ.setdefault("DATABRICKS_CONFIG_PROFILE", "group-demo")

from agent import AGENT
from mlflow.types.responses import ResponsesAgentRequest

TEST_QUERIES = [
    "Show me today's appointments."
]


def extract_final_response(response) -> str:
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
    for q in TEST_QUERIES:
        print(f"\n{'='*60}")
        print(f"QUERY: {q}")
        print(f"{'='*60}")
        request = ResponsesAgentRequest(input=[{"role": "user", "content": q}])
        response = AGENT.predict(request)
        print(extract_final_response(response))
