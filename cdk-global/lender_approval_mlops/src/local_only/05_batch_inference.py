# Databricks notebook source
# MAGIC %md
# MAGIC # Batch inference – Champion model (MLOps advanced)
# MAGIC Use Feature Engineering client score_batch; save predictions to offline inference table for monitoring.

# COMMAND ----------

#dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
#dbutils.widgets.text("schema", "cdk", "Schema")
catalog = "mfg_mc_se_sa"
db = "cdk"
app_ids_table_name = "lender_approval_app_ids"
experiment_name = "/Shared/lender_approval_mlops"
# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

import os
os.environ["DATABRICKS_CONFIG_PROFILE"] = "group-demo"
model_name = "mfg_mc_se_sa.cdk.lender_approval_model"
from databricks.feature_engineering import FeatureEngineeringClient
from datetime import datetime
from pyspark.sql import functions as F
import mlflow
from mlflow.tracking.client import MlflowClient
from databricks.connect import DatabricksSession
mlflow.set_tracking_uri(f"databricks://group-demo")
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(experiment_name)

spark = DatabricksSession.builder.profile("group-demo").serverless().getOrCreate()
fe = FeatureEngineeringClient()
client = MlflowClient()

model_alias = "Champion"
model_uri = f"models:/{model_name}@{model_alias}"
env_manager = "local"

# Load application IDs to score (from 01 feature engineering)
inference_df = spark.read.table(f"{catalog}.{db}.{app_ids_table_name}").limit(500)
inference_df = inference_df.withColumn("split", F.lit("test"))
preds_df = fe.score_batch(
    df=inference_df,
    model_uri=model_uri,
    result_type="long"
)
#display(preds_df)
print(preds_df.head(20))
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
