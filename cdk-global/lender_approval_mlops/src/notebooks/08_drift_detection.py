# Databricks notebook source
# MAGIC %md
# MAGIC # Lender approval – drift detection (MLOps advanced)
# MAGIC Query Lakehouse Monitoring drift/profile metrics and set task value for conditional retrain (e.g. If/else in jobs).

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")
dbutils.widgets.dropdown("perf_metric", "f1_score.macro", ["accuracy_score", "precision.weighted", "recall.weighted", "f1_score.macro"])
dbutils.widgets.dropdown("drift_metric", "js_distance", ["chi_squared_test.statistic", "js_distance", "tv_distance", "l_infinity_distance"])
dbutils.widgets.text("model_id", "*", "Model version filter")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import MonitorRefreshInfoState
from pyspark.sql.functions import col, first

w = WorkspaceClient()
metric = dbutils.widgets.get("perf_metric")
drift = dbutils.widgets.get("drift_metric")
model_id = dbutils.widgets.get("model_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Refresh monitor (if new data in inference table)

# COMMAND ----------

refresh_info = w.quality_monitors.run_refresh(table_name=f"{catalog}.{db}.{inference_table_name}")
while refresh_info.state in (MonitorRefreshInfoState.PENDING, MonitorRefreshInfoState.RUNNING):
    refresh_info = w.quality_monitors.get_refresh(
        table_name=f"{catalog}.{db}.{inference_table_name}", refresh_id=refresh_info.refresh_id
    )
    time.sleep(30)

# COMMAND ----------

monitor_info = w.quality_monitors.get(table_name=f"{catalog}.{db}.{inference_table_name}")
drift_table_name = monitor_info.drift_metrics_table_name
profile_table_name = monitor_info.profile_metrics_table_name

# COMMAND ----------

# MAGIC %md
# MAGIC ## Performance metrics from profile table

# COMMAND ----------

performance_metrics_df = spark.sql(f"""
  SELECT
    window.start AS time,
    {metric} AS performance_metric,
    Model_Version AS `Model Id`
  FROM {profile_table_name}
  WHERE log_type = 'INPUT'
    AND column_name = ':table'
    AND slice_key IS NULL AND slice_value IS NULL
    AND (Model_Version = '{model_id}' OR '{model_id}' = '*')
  ORDER BY window.start
""")
display(performance_metrics_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Drift metrics (prediction and label)

# COMMAND ----------

drift_metrics_df = spark.sql(f"""
  SELECT
    window.start AS time,
    column_name,
    {drift} AS drift_metric,
    Model_Version AS `Model Id`
  FROM {drift_table_name}
  WHERE column_name IN ('prediction', 'label_approved')
    AND slice_key IS NULL AND slice_value IS NULL
    AND (Model_Version = '{model_id}' OR '{model_id}' = '*')
    AND drift_type = 'CONSECUTIVE'
  ORDER BY window.start
""")
display(drift_metrics_df)

# COMMAND ----------

# Unstack and join with performance
unstacked_drift = (
    drift_metrics_df.groupBy("time", "`Model Id`")
    .pivot("column_name")
    .agg(first("drift_metric"))
    .orderBy("time")
) if not drift_metrics_df.isEmpty() else None

all_metrics_df = performance_metrics_df
if unstacked_drift is not None:
    all_metrics_df = performance_metrics_df.join(unstacked_drift, on=["time", "Model Id"], how="left")
display(all_metrics_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Count violations (thresholds) and set task value for job branching

# COMMAND ----------

performance_violation_count = all_metrics_df.filter(col("performance_metric") < 0.5).count()
drift_violation_count = 0
if not drift_metrics_df.isEmpty() and unstacked_drift is not None:
    drift_violation_count = all_metrics_df.filter(
        (col("label_approved").isNotNull() & (col("label_approved") > 0.19)) |
        (col("prediction").isNotNull() & (col("prediction") > 0.19))
    ).count()
all_violations_count = performance_violation_count + drift_violation_count

print(f"Performance violations (metric < 0.5): {performance_violation_count}")
print(f"Drift violations: {drift_violation_count}")
print(f"Total violations: {all_violations_count}")

dbutils.jobs.taskValues.set(key="all_violations_count", value=all_violations_count)
