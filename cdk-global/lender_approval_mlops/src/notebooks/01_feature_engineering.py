# Databricks notebook source
# MAGIC %md
# MAGIC # Lender approval – feature engineering (MLOps advanced)
# MAGIC Build feature table and label table from gold, optional on-demand feature function, and table of application IDs for batch inference.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

from datetime import datetime
from pyspark.sql import functions as F

# Read gold (from SDP pipeline in same catalog.schema)
gold_full = f"{catalog}.{schema}.{gold_table_name}"
df = spark.table(gold_full)
display(df.limit(5))

# COMMAND ----------

# Add scoring timestamp and prepare feature + label tables
this_time = (datetime.now()).timestamp()
df_ts = df.withColumn("transaction_ts", F.lit(this_time).cast("timestamp"))

# Label table: application_id, transaction_ts, approved, split (avoid label leakage)
labels_df = df_ts.select("application_id", "transaction_ts", "approved", "split")
labels_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{catalog}.{schema}.{label_table_name}"
)

# Feature table: drop label and split; keep keys + transaction_ts
feature_cols = [c for c in df_ts.columns if c not in ("approved", "split")]
features_df = df_ts.select(feature_cols)

# COMMAND ----------

from databricks.feature_engineering import FeatureEngineeringClient

fe = FeatureEngineeringClient()
spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.{feature_table_name}")

lender_feature_table = fe.create_table(
    name=f"{catalog}.{schema}.{feature_table_name}",
    primary_keys=["application_id", "transaction_ts"],
    schema=features_df.schema,
    timeseries_columns="transaction_ts",
    description="Lender approval features from gold_lender_features (income, credit_score, employment_years, debt_to_income, loan_amount, loan_purpose).",
)
fe.write_table(
    name=f"{catalog}.{schema}.{feature_table_name}",
    df=features_df,
    mode="merge",
)

# COMMAND ----------

# On-demand feature function: affordability ratio (loan_amount / income)
spark.sql(f"""
  CREATE OR REPLACE FUNCTION {catalog}.{schema}.affordability_ratio(income_in DOUBLE, loan_amount_in DOUBLE)
  RETURNS FLOAT
  LANGUAGE PYTHON
  COMMENT "Loan amount as fraction of income (lower is more affordable)"
  AS $$
  if income_in and income_in > 0:
    return float(loan_amount_in / income_in)
  return 0.0
  $$
""")

# COMMAND ----------

# Table of application IDs to score (for batch inference). Use test split IDs.
app_ids_df = spark.table(f"{catalog}.{schema}.{label_table_name}") \
    .filter("split = 'test'") \
    .select("application_id", "transaction_ts")
app_ids_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{catalog}.{schema}.{app_ids_table_name}"
)
print(f"Created {app_ids_table_name} with {app_ids_df.count()} rows for batch scoring.")
