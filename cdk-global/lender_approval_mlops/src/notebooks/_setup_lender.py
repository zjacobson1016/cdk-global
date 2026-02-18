# Databricks notebook source
# MAGIC %md
# MAGIC # Lender Approval MLOps – config
# MAGIC Sets catalog, schema, and table/model names. Other notebooks use these after %run this notebook.

# COMMAND ----------

try:
    catalog = dbutils.widgets.get("catalog")
except Exception:
    catalog = "mfg_mc_se_sa"
try:
    schema = dbutils.widgets.get("schema")
except Exception:
    schema = "cdk"

db = schema  # alias used in advanced notebooks

# Table names (unqualified; use catalog.db.table when needed)
feature_table_name = "lender_approval_feature_table"
label_table_name = "lender_approval_label_table"
app_ids_table_name = "lender_approval_app_ids"       # application_id + transaction_ts for batch scoring
offline_inference_table_name = "lender_approval_offline_inference"

# Gold table produced by SDP (source for 01 feature engineering)
gold_table_name = "gold_lender_features"

# Unity Catalog model and experiment
model_name = f"{catalog}.{db}.lender_approval_model"
xp_path = "/Shared"
xp_name = "lender_approval_mlops"
experiment_name = f"{xp_path}/{xp_name}"

# Label column for training/validation
label_col = "approved"
pos_label = 1  # binary: 1 = approved

# Serving & monitoring (notebooks 06, 07, 08)
online_store_name = f"lender-approval-online-{schema}"[:64]  # name length limit
online_feature_table_name = "lender_approval_feature_online_table"
endpoint_name = f"lender_approval_serving_{schema}"[:50]    # endpoint name length limit
inference_table_name = "lender_approval_inference_table"    # unified table for monitoring (offline + labels)
baseline_table_name = "lender_approval_baseline"
