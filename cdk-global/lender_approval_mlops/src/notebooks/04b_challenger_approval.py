# Databricks notebook source
# MAGIC %md
# MAGIC # Challenger approval – promote to Champion (MLOps advanced)
# MAGIC Check Approval_Check tag; if approved, set Champion alias.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")
dbutils.widgets.text("model_version", "", "Model version to promote")
dbutils.widgets.text("approval_tag_name", "Approval_Check", "Approval tag to check")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

from mlflow.tracking.client import MlflowClient

client = MlflowClient(registry_uri="databricks-uc")
model_version_param = dbutils.widgets.get("model_version").strip()
tag_name = dbutils.widgets.get("approval_tag_name")

if model_version_param:
    model_version = model_version_param
else:
    model_version = client.get_model_version_by_alias(model_name, "Challenger").version

tags = client.get_model_version(model_name, model_version).tags
if tag_name not in tags:
    raise Exception("Model version not approved for deployment (missing tag)")
if tags.get(tag_name).lower() != "approved":
    raise Exception("Model version not approved for deployment (tag != approved)")

client.set_registered_model_alias(model_name, "Champion", str(model_version))
print(f"Champion alias set on {model_name} version {model_version}. Next: 05_batch_inference.")
