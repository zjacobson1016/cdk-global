# Databricks notebook source
# MAGIC %md
# MAGIC # Test Invoice Processing Agent — HITL Approval Workflow
# MAGIC Runs test cases against the agent locally on a Databricks cluster.

# COMMAND ----------

# MAGIC %pip install mlflow==3.6.0 databricks-langchain langgraph==0.3.4 pydantic databricks-agents slack_sdk "psycopg[binary]>=3.0" "databricks-sdk>=0.68.0"
# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ./agent

# COMMAND ----------

from mlflow.types.responses import ResponsesAgentRequest, ChatContext

# COMMAND ----------

# MAGIC %md
# MAGIC ## General Queries (existing functionality)

# COMMAND ----------

general_tests = [
    "Give me a summary of all invoices currently in the system.",
    "How is AutoZone Commercial performing as a supplier?",
    "Show me all invoices routed to EXCEPTION_REVIEW.",
]

for i, question in enumerate(general_tests):
    print(f"\n{'='*60}")
    print(f"GENERAL TEST {i+1}: {question}")
    print(f"{'='*60}")

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": question}],
        context=ChatContext(user_id="ap-clerk@sunsetcdjr.com"),
    )
    result = AGENT.predict(request)
    for item in result.output:
        item_dict = item.model_dump(exclude_none=True)
        if item_dict.get("type") == "message":
            print(f"\nAgent: {item_dict.get('content', [{}])[0].get('text', 'No text')}")
        else:
            print(f"\n[{item_dict.get('type', 'unknown')}]: {str(item_dict)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Invoice Processing Pipeline (Lookup → Classify → Match → Submit)

# COMMAND ----------

process_tests = [
    "Process invoice INV-001 for approval.",
    "Review and submit INV-025 through the approval pipeline.",
]

for i, question in enumerate(process_tests):
    print(f"\n{'='*60}")
    print(f"PROCESS TEST {i+1}: {question}")
    print(f"{'='*60}")

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": question}],
        context=ChatContext(user_id="ap-clerk@sunsetcdjr.com"),
    )
    result = AGENT.predict(request)
    for item in result.output:
        item_dict = item.model_dump(exclude_none=True)
        if item_dict.get("type") == "message":
            print(f"\nAgent: {item_dict.get('content', [{}])[0].get('text', 'No text')}")
        else:
            print(f"\n[{item_dict.get('type', 'unknown')}]: {str(item_dict)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Approval Actions

# COMMAND ----------

approval_tests = [
    "I'm the Service Manager. Approve INV-001.",
    "As Parts Director, reject INV-025 — the pricing doesn't match our contract rates.",
    "Escalate INV-010 to the next level.",
]

for i, question in enumerate(approval_tests):
    print(f"\n{'='*60}")
    print(f"APPROVAL TEST {i+1}: {question}")
    print(f"{'='*60}")

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": question}],
        context=ChatContext(user_id="service-mgr@sunsetcdjr.com"),
    )
    result = AGENT.predict(request)
    for item in result.output:
        item_dict = item.model_dump(exclude_none=True)
        if item_dict.get("type") == "message":
            print(f"\nAgent: {item_dict.get('content', [{}])[0].get('text', 'No text')}")
        else:
            print(f"\n[{item_dict.get('type', 'unknown')}]: {str(item_dict)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Status & Queue Queries

# COMMAND ----------

status_tests = [
    "What's the approval status of INV-001?",
    "I'm the Service Manager — what invoices are pending my approval?",
    "Give me a summary of the approval pipeline.",
]

for i, question in enumerate(status_tests):
    print(f"\n{'='*60}")
    print(f"STATUS TEST {i+1}: {question}")
    print(f"{'='*60}")

    request = ResponsesAgentRequest(
        input=[{"role": "user", "content": question}],
        context=ChatContext(user_id="service-mgr@sunsetcdjr.com"),
    )
    result = AGENT.predict(request)
    for item in result.output:
        item_dict = item.model_dump(exclude_none=True)
        if item_dict.get("type") == "message":
            print(f"\nAgent: {item_dict.get('content', [{}])[0].get('text', 'No text')}")
        else:
            print(f"\n[{item_dict.get('type', 'unknown')}]: {str(item_dict)[:200]}")

# COMMAND ----------

print(f"\n{'='*60}")
print("All tests completed!")
