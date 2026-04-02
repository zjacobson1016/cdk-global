# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy Service Advisor Agent
# MAGIC Deploys the registered agent to a Model Serving endpoint.

# COMMAND ----------

# MAGIC %pip install databricks-agents
# MAGIC %restart_python

# COMMAND ----------

from databricks import agents
import mlflow

model_name = "mfg_mc_se_sa.cdk_service.service_advisor_agent"
client = mlflow.MlflowClient()
versions = client.search_model_versions(f"name='{model_name}'")
latest = max(versions, key=lambda v: int(v.version))
version = latest.version

print(f"Deploying {model_name} version {version}...")

# COMMAND ----------

deployment = agents.deploy(
    model_name,
    version,
    tags={"source": "dab", "use_case": "service_advisor", "customer": "cdk"},
)

print(f"Deployment complete!")
print(f"Endpoint: {deployment.endpoint_name}")
print(f"Endpoint URL: {deployment.endpoint_url}")
