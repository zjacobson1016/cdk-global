# Databricks notebook source
# MAGIC %md
# MAGIC # Batch inference – Champion model (MLOps advanced)
# MAGIC Uses `fe.score_batch` so that feature lookups (including
# MAGIC `transaction_ts` point-in-time join) happen in Spark, then the
# MAGIC pyfunc wrapper applies deterministic rules and returns structured
# MAGIC predictions with reasoning.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")

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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Score with Champion model
# MAGIC `fe.score_batch` handles the feature-table join (using `application_id`
# MAGIC *and* `transaction_ts` for point-in-time lookup), evaluates the on-demand
# MAGIC Feature Functions, and feeds the result to the pyfunc model.

# COMMAND ----------

# Load the scoring table – it already has application_id + transaction_ts
inference_df = spark.read.table(f"{catalog}.{schema}.{app_ids_table_name}").limit(500)

# Debug: confirm columns before scoring
print(f"Inference table columns: {inference_df.columns}")
print(f"Row count: {inference_df.count()}")
inference_df.show(3, truncate=False)

# COMMAND ----------

# fe.score_batch uses the Spark DataFrame directly, so
# the timestamp-lookup key is found by the FE wrapper.
preds_df = fe.score_batch(
    df=inference_df,
    model_uri=model_uri,
)

# Show what columns we got back
print(f"Scored columns: {preds_df.columns}")
preds_df.show(3, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Build final scored DataFrame
# MAGIC If the pyfunc wrapper returned all structured columns (prediction,
# MAGIC ml_prediction, ml_probability, income_check, id_check, decision_reason),
# MAGIC use them directly.  Otherwise, re-derive the reasoning from the features
# MAGIC that `fe.score_batch` already looked up.

# COMMAND ----------

# Check if the pyfunc wrapper's structured columns came through
has_structured_output = all(
    c in preds_df.columns
    for c in ["ml_prediction", "ml_probability", "income_check", "id_check", "decision_reason"]
)

if has_structured_output:
    # All columns from the pyfunc wrapper are present – select directly
    print("Using pyfunc structured output.")
    scored_df = preds_df.select(
        "application_id",
        "transaction_ts",
        F.col("prediction").alias("prediction"),
        "ml_prediction",
        "ml_probability",
        "income_check",
        "id_check",
        "decision_reason",
    )
else:
    # score_batch only gave us a single "prediction" column (the final
    # decision after rules).  Re-derive reasoning from the Feature-Function
    # columns that score_batch already looked up.
    print("Deriving decision reasoning from feature columns post-hoc.")
    scored_df = preds_df.select(
        "application_id",
        "transaction_ts",
        F.col("prediction").cast("int").alias("prediction"),
        # income_validated & id_not_expired were computed by Feature Functions
        F.coalesce(F.col("income_validated").cast("int"), F.lit(-1)).alias("income_check_val"),
        F.coalesce(F.col("id_not_expired").cast("int"), F.lit(-1)).alias("id_check_val"),
    ).withColumn(
        "income_check",
        F.when(F.col("income_check_val") == 1, "PASS")
         .when(F.col("income_check_val") == 0, "FAIL")
         .otherwise("MISSING"),
    ).withColumn(
        "id_check",
        F.when(F.col("id_check_val") == 1, "PASS")
         .when(F.col("id_check_val") == 0, "FAIL")
         .otherwise("MISSING"),
    ).withColumn(
        "decision_reason",
        F.when(
            (F.col("income_check_val") == 0) | (F.col("id_check_val") == 0),
            F.concat(
                F.lit("DENIED by rules: "),
                F.concat_ws(
                    " + ",
                    F.when(F.col("income_check_val") == 0, F.lit("Income mismatch (pay stub vs application)")),
                    F.when(F.col("id_check_val") == 0, F.lit("Expired photo ID")),
                ),
            ),
        ).when(
            F.col("prediction") == 1,
            F.when(
                (F.col("income_check_val") != -1) & (F.col("id_check_val") != -1),
                F.lit("APPROVED by ML model (all checks passed)"),
            ).otherwise(F.lit("APPROVED by ML model (pending doc verification)")),
        ).otherwise(F.lit("DENIED by ML model")),
    ).drop("income_check_val", "id_check_val")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Decision summary

# COMMAND ----------

print("Decision breakdown:")
scored_df.groupBy("decision_reason").count().orderBy(F.desc("count")).show(truncate=False)

print("Income check distribution:")
scored_df.groupBy("income_check").count().show()

print("ID check distribution:")
scored_df.groupBy("id_check").count().show()

print("Sample predictions:")
scored_df.show(10, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save to offline inference table

# COMMAND ----------

model_version = client.get_model_version_by_alias(model_name, model_alias).version
offline_df = (
    scored_df
    .withColumn("model_version", F.lit(model_version))
    .withColumn("inference_timestamp", F.lit(datetime.now()))
)

offline_df.write.mode("append").option("overwriteSchema", "true").saveAsTable(
    f"{catalog}.{schema}.{offline_inference_table_name}"
)

total = offline_df.count()
rule_overrides = offline_df.filter(F.col("decision_reason").like("%rules%")).count()
print(f"Saved {total} predictions to {offline_inference_table_name}")
print(f"  ML-only decisions: {total - rule_overrides}")
print(f"  Rule overrides:    {rule_overrides} ({rule_overrides/max(total,1)*100:.1f}%)")
