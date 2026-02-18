# Databricks notebook source
# MAGIC %md
# MAGIC # Challenger model validation (MLOps advanced)
# MAGIC Run checks (description, prediction, artifacts, metric vs Champion), set tags, then set Approval_Check=approved.

# COMMAND ----------

# dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
# dbutils.widgets.text("schema", "cdk", "Schema")
# dbutils.widgets.text("model_version", "", "Model version (optional; default = latest Challenger)")
catalog = "mfg_mc_se_sa"
schema = "cdk"
db = schema
label_table_name = "lender_approval_label_table"
# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

import os
os.environ["DATABRICKS_CONFIG_PROFILE"] = "group-demo"
model_name = "mfg_mc_se_sa.cdk.lender_approval_model"
import mlflow
from mlflow.tracking.client import MlflowClient
from databricks.feature_engineering import FeatureEngineeringClient
from databricks.connect import DatabricksSession
spark = DatabricksSession.builder.profile("group-demo").serverless().getOrCreate()
mlflow.set_tracking_uri(f"databricks://group-demo")
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experiment_name)
client = MlflowClient()
#Access locally with this workaround: https://community.databricks.com/t5/data-engineering/featureengineeringclient-and-databricks-connect/td-p/96918
fe = FeatureEngineeringClient()

#model_version_param = dbutils.widgets.get("model_version").strip()

model_version = client.get_model_version_by_alias(model_name, "Challenger").version
print(f"Validating {model_name} version {model_version}")

model_details = client.get_model_version(model_name, str(model_version))
run_info = client.get_run(model_details.run_id)

# COMMAND ----------

# Description check
has_description = bool(model_details.description and len(model_details.description) > 20)
client.set_model_version_tag(name=model_name, version=str(model_version), key="has_description", value=has_description)
print(f"has_description: {has_description}")

# COMMAND ----------

# Prediction check: score_batch on a small set
try:
    labels_df = spark.read.table(f"{catalog}.{db}.{label_table_name}").filter("split = 'test'").limit(10)
    preds = fe.score_batch(
        df=labels_df,
        model_uri=f"models:/{model_name}/{model_version}",
        result_type="long",
        env_manager="virtualenv",
    )
    display(preds)
    predicts_check = True
except Exception as e:
    print(e)
    predicts_check = False
client.set_model_version_tag(name=model_name, version=str(model_version), key="predicts", value=predicts_check)
print(f"predicts: {predicts_check}")

# COMMAND ----------

# Metric check: compare Challenger test_f1_score to Champion
model_run_id = model_details.run_id
challenger_f1 = mlflow.get_run(model_run_id).data.metrics.get("test_f1_score")
if challenger_f1 is None:
    metric_passed = True
    print("No test_f1_score on run; accepting.")
else:
    try:
        champion_mv = client.get_model_version_by_alias(model_name, "Champion")
        champion_f1 = mlflow.get_run(champion_mv.run_id).data.metrics.get("test_f1_score") or 0
        metric_passed = challenger_f1 >= champion_f1
        print(f"Champion F1: {champion_f1}, Challenger F1: {challenger_f1}, passed: {metric_passed}")
    except Exception:
        metric_passed = True
        print("No Champion yet; accepting Challenger.")
client.set_model_version_tag(name=model_name, version=str(model_version), key="metric_f1_passed", value=metric_passed)

# COMMAND ----------

# Mark as approved for deployment (04b checks this tag)
#client.set_model_version_tag(name=model_name, version=str(model_version), key="Approval_Check", value="approved")
#print("Set Approval_Check=approved. Run 04b_challenger_approval to promote to Champion.")
