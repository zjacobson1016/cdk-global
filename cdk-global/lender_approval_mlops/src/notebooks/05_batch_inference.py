# Databricks notebook source
# MAGIC %md
# MAGIC # Batch inference – Champion model (MLOps advanced)
# MAGIC Use Feature Engineering client score_batch; save predictions to offline inference table for monitoring.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

from databricks.feature_engineering import FeatureEngineeringClient
from datetime import datetime
from pyspark.sql import functions as F
from mlflow.tracking.client import MlflowClient

fe = FeatureEngineeringClient()
client = MlflowClient(registry_uri="databricks-uc")

model_alias = "Champion"
model_uri = f"models:/{model_name}@{model_alias}"
env_manager = "virtualenv"

# Load application IDs to score (from 01 feature engineering)
inference_df = spark.read.table(f"{catalog}.{db}.{app_ids_table_name}").limit(500)

preds_df = fe.score_batch(
    df=inference_df,
    model_uri=model_uri,
    result_type="long",
    env_manager=env_manager,
)
display(preds_df)

# COMMAND ----------

# Save to offline inference table for monitoring/drift
model_version = client.get_model_version_by_alias(model_name, model_alias).version
offline_df = preds_df.withColumn("model_version", F.lit(model_version)).withColumn(
    "inference_timestamp", F.lit(datetime.now())
)
offline_df.write.mode("append").option("overwriteSchema", "true").saveAsTable(
    f"{catalog}.{schema}.{offline_inference_table_name}"
)
print(f"Saved predictions to {offline_inference_table_name}")
