# Databricks notebook source
# MAGIC %md
# MAGIC # Log & Register Document Parsing Agent
# MAGIC Logs the `DocumentParsingAgent` to MLflow and registers it in Unity Catalog.
# MAGIC
# MAGIC The agent wraps `ai_parse_document` + `ai_query` in a parameterized
# MAGIC `ResponsesAgent` — model, prompt, response schema, temperature, and
# MAGIC warehouse are all configurable via environment variables on the endpoint.

# COMMAND ----------

# MAGIC %pip install mlflow==3.6.0 databricks-langchain langchain-core pydantic databricks-agents "databricks-sdk>=0.68.0"
# MAGIC %restart_python

# COMMAND ----------

import os
import mlflow
from mlflow.models.resources import (
    DatabricksServingEndpoint,
    DatabricksSQLWarehouse,
)
from document_parsing_agent import AGENT, DEFAULT_MODEL_ENDPOINT

mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------

CATALOG = os.environ.get("CATALOG", "mfg_mc_se_sa")
SCHEMA = os.environ.get("SCHEMA", "cdk")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")

resources = [
    DatabricksServingEndpoint(endpoint_name=AGENT.model_endpoint),
]
if WAREHOUSE_ID:
    resources.append(DatabricksSQLWarehouse(warehouse_id=WAREHOUSE_ID))

print(f"Resources: {[str(r) for r in resources]}")

# COMMAND ----------

input_example = {
    "input": [
        {
            "role": "user",
            "content": "Parse the invoice at /Volumes/mfg_mc_se_sa/cdk/invoices/INV-001.pdf",
        }
    ]
}

with mlflow.start_run():
    model_info = mlflow.pyfunc.log_model(
        name="document_parsing_agent",
        python_model="document_parsing_agent.py",
        input_example=input_example,
        resources=resources,
        pip_requirements=[
            "mlflow==3.6.0",
            "databricks-langchain",
            "langchain-core",
            "pydantic",
            "databricks-agents",
            "databricks-sdk>=0.68.0",
        ],
    )
    print(f"Model URI: {model_info.model_uri}")

# COMMAND ----------

model_name = f"{CATALOG}.{SCHEMA}.document_parsing_agent"
uc_model_info = mlflow.register_model(
    model_uri=model_info.model_uri,
    name=model_name,
)
print(f"Registered: {uc_model_info.name} version {uc_model_info.version}")
