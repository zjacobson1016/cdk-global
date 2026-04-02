"""Flask conversation UI for the Service Advisor Agent.

Serves a chat interface that proxies messages to the deployed agent
endpoint on Databricks Model Serving. Uses app-level (service principal)
auth via SDK Config() for the serving endpoint call.
"""

import os
import json
import requests as http_requests
from flask import Flask, request, jsonify, render_template
from databricks.sdk.core import Config

app = Flask(__name__)
cfg = Config()

HOST = cfg.host.rstrip("/")
if not HOST.startswith("https://"):
    HOST = f"https://{HOST}"

AGENT_ENDPOINT = os.getenv(
    "SERVING_ENDPOINT_NAME",
    "agents_mfg_mc_se_sa-cdk_service-service_advisor_agent",
)
FORMAT_MODEL = "databricks-claude-opus-4-6"

FORMAT_SYSTEM_PROMPT = (
    "You are a formatting assistant. The user asked a question to a service "
    "advisor agent and received a raw response. Rewrite the raw response into "
    "a clean, well-structured, human-readable answer using markdown. "
    "Use tables for tabular data, bullet points for lists, and bold for key values. "
    "Do NOT add information that is not in the raw response. "
    "Do NOT mention that you are reformatting. Just present the answer directly."
)


def _to_str(val) -> str:
    if isinstance(val, str):
        return val
    return json.dumps(val, default=str)


def _extract_text(data: dict) -> str:
    if "output" in data:
        output = data["output"]
        if isinstance(output, list):
            for msg in reversed(output):
                if isinstance(msg, dict) and msg.get("role") == "assistant":
                    return _to_str(msg.get("content", ""))
            return _to_str(output[-1] if output else "")
        if isinstance(output, dict) and "content" in output:
            return _to_str(output["content"])
        return _to_str(output)

    if "choices" in data:
        return _to_str(data["choices"][0]["message"]["content"])

    return json.dumps(data, default=str)


def _format_with_llm(user_question: str, raw_response: str) -> str:
    headers = cfg.authenticate()
    headers["Content-Type"] = "application/json"

    resp = http_requests.post(
        f"{HOST}/serving-endpoints/{FORMAT_MODEL}/invocations",
        headers=headers,
        json={
            "messages": [
                {"role": "system", "content": FORMAT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User question: {user_question}\n\n"
                        f"Raw agent response:\n{raw_response}"
                    ),
                },
            ],
            "max_tokens": 2048,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _call_agent(messages: list[dict]) -> str:
    headers = cfg.authenticate()
    headers["Content-Type"] = "application/json"

    resp = http_requests.post(
        f"{HOST}/serving-endpoints/{AGENT_ENDPOINT}/invocations",
        headers=headers,
        json={"input": messages},
        timeout=120,
    )
    resp.raise_for_status()
    raw = _extract_text(resp.json())

    user_question = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_question = msg.get("content", "")
            break

    try:
        return _format_with_llm(user_question, raw)
    except Exception:
        return raw


@app.route("/")
def index():
    return render_template("chat.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json()
    messages = body.get("messages", [])

    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    try:
        reply = _call_agent(messages)
        return jsonify({"reply": reply})
    except http_requests.HTTPError as e:
        return jsonify({"error": f"Agent error: {e.response.status_code}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/debug", methods=["POST"])
def debug():
    body = request.get_json()
    messages = body.get("messages", [{"role": "user", "content": "hello"}])
    headers = cfg.authenticate()
    headers["Content-Type"] = "application/json"
    resp = http_requests.post(
        f"{HOST}/serving-endpoints/{AGENT_ENDPOINT}/invocations",
        headers=headers,
        json={"input": messages},
        timeout=120,
    )
    return jsonify({"status_code": resp.status_code, "raw": resp.json()})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
