# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy Invoice Processing Agent
# MAGIC Deploys the registered agent to a Model Serving endpoint.

# COMMAND ----------

# MAGIC %pip install databricks-agents
# MAGIC %restart_python

# COMMAND ----------

from databricks import agents

model_name = "mfg_mc_se_sa.cdk.parts_invoice_agent"
version = "7"

print(f"Deploying {model_name} version {version}...")

# COMMAND ----------

deployment = agents.deploy(
    model_name,
    version,
    tags={"source": "mcp", "use_case": "parts_invoice_processing", "customer": "cdk"},
)

print(f"Deployment complete!")
print(f"Endpoint: {deployment.endpoint_name}")
print(f"Endpoint URL: {deployment.endpoint_url}")
