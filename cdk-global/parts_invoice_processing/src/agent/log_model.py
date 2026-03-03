# Databricks notebook source
# MAGIC %md
# MAGIC # Log & Register Invoice Processing Agent
# MAGIC Logs the agent to MLflow and registers it in Unity Catalog.
# MAGIC Includes approval_tools.py and slack_notifier.py as code_paths.

# COMMAND ----------

# MAGIC %pip install mlflow==3.6.0 databricks-langchain langgraph==0.3.4 pydantic databricks-agents slack_sdk "psycopg[binary]>=3.0" "databricks-sdk>=0.68.0"
# MAGIC %restart_python

# COMMAND ----------

# COMMAND ----------

import os
import mlflow
from mlflow.models.resources import DatabricksServingEndpoint, DatabricksFunction, DatabricksLakebase, DatabricksGenieSpace
from unitycatalog.ai.langchain.toolkit import UnityCatalogTool
from agent import AGENT, LLM_ENDPOINT

mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------
CATALOG = os.environ.get("CATALOG", "mfg_mc_se_sa")
SCHEMA = os.environ.get("SCHEMA", "cdk")
LAKEBASE_INSTANCE = os.environ.get("LAKEBASE_INSTANCE_NAME", "cdk-invoice-dev")
GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "01f115d7a668194eba3e8bcf9297cc05")

resources = [
    DatabricksServingEndpoint(endpoint_name=LLM_ENDPOINT),
    DatabricksLakebase(database_instance_name=LAKEBASE_INSTANCE),
    DatabricksGenieSpace(genie_space_id=GENIE_SPACE_ID),
    DatabricksFunction(function_name=f"{CATALOG}.{SCHEMA}._ask_invoice_genie_impl"),
]

for tool in AGENT.uc_tools:
    if isinstance(tool, UnityCatalogTool):
        resources.append(DatabricksFunction(function_name=tool.uc_function_name))

print(f"Resources: {[str(r) for r in resources]}")

# COMMAND ----------

code_paths = [
    "approval_tools.py",
    "slack_notifier.py",
]
print(f"Code paths: {code_paths}")

# COMMAND ----------

input_example = {
    "input": [{"role": "user", "content": "Process invoice INV-001 for approval."}]
}

with mlflow.start_run():
    model_info = mlflow.pyfunc.log_model(
        name="agent",
        python_model="agent.py",
        code_paths=code_paths,
        input_example=input_example,
        resources=resources,
        pip_requirements=[
            "mlflow==3.6.0",
            "databricks-langchain",
            "langgraph==0.3.4",
            "pydantic",
            "databricks-agents",
            "databricks-sdk>=0.68.0",
            "slack_sdk",
            "psycopg[binary]>=3.0",
        ],
    )
    print(f"Model URI: {model_info.model_uri}")

# COMMAND ----------

model_name = f"{CATALOG}.{SCHEMA}.parts_invoice_agent"    
uc_model_info = mlflow.register_model(
    model_uri=model_info.model_uri,
    name=model_name,
)
print(f"Registered: {uc_model_info.name} version {uc_model_info.version}")
