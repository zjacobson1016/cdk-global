# Databricks notebook source
# MAGIC %md
# MAGIC # Register best run to Unity Catalog (Challenger)
# MAGIC Find best HPO run, register model to UC, set Challenger alias and description.

# COMMAND ----------

dbutils.widgets.text("catalog", "main", "Catalog")
dbutils.widgets.text("schema", "lender_approval", "Schema")
dbutils.widgets.text("run_id", "", "Run ID (optional; leave empty to use best run by test_f1_score)")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

import mlflow
from mlflow.tracking.client import MlflowClient

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experiment_name)
client = MlflowClient()

run_id_param = dbutils.widgets.get("run_id").strip()
if run_id_param:
    run_id = run_id_param
    print(f"Using provided run_id: {run_id}")
else:
    runs = mlflow.search_runs(
        experiment_names=[experiment_name],
        order_by=["metrics.test_f1_score DESC"],
        max_results=1,
        filter_string="status = 'FINISHED'",
    )
    if runs.empty:
        raise ValueError("No finished runs found. Run 02_model_training_hpo_optuna first.")
    run_id = runs.iloc[0]["run_id"]
    print(f"Best run_id: {run_id}")

# COMMAND ----------

model_details = mlflow.register_model(f"runs:/{run_id}/model", model_name)
print(f"Registered model version {model_details.version} to {model_name}")

# COMMAND ----------

client.set_registered_model_alias(model_name, "Challenger", str(model_details.version))
client.update_registered_model(name=model_name, description="Lender approval binary classifier (approved/denied). Trained with Feature Store and Optuna HPO.")
print("Set Challenger alias and description. Next: run 04a_challenger_validation then 04b_challenger_approval.")
