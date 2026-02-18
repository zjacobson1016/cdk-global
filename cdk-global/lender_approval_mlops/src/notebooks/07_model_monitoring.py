# Databricks notebook source
# MAGIC %md
# MAGIC # Lender approval – model monitoring (MLOps advanced)
# MAGIC Attach Lakehouse Monitoring to the inference table for profile and drift metrics.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

import os
import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import (
    MonitorInferenceLog,
    MonitorInferenceLogProblemType,
    MonitorCronSchedule,
    MonitorInfoStatus,
    MonitorRefreshInfoState,
)

w = WorkspaceClient()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create unified inference table (offline predictions + labels when available)

# COMMAND ----------

spark.sql(f"""
  CREATE OR REPLACE TABLE {catalog}.{db}.{inference_table_name} AS
  SELECT
    i.application_id,
    i.transaction_ts,
    CAST(i.prediction AS LONG) AS prediction,
    i.income_check,
    i.id_check,
    i.decision_reason,
    i.model_version,
    i.inference_timestamp,
    CAST(l.approved AS LONG) AS label_approved
  FROM {catalog}.{db}.{offline_inference_table_name} i
  LEFT JOIN {catalog}.{db}.{label_table_name} l
    ON i.application_id = l.application_id
       AND (i.transaction_ts = l.transaction_ts OR i.transaction_ts IS NULL)
  ORDER BY i.inference_timestamp
""")
spark.sql(f"ALTER TABLE {catalog}.{db}.{inference_table_name} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create baseline table (reference for drift)

# COMMAND ----------

spark.sql(f"""
  CREATE OR REPLACE TABLE {catalog}.{db}.{baseline_table_name} AS
  SELECT CAST(i.prediction AS LONG) AS prediction, i.model_version, i.inference_timestamp, CAST(l.approved AS LONG) AS label_approved
  FROM {catalog}.{db}.{offline_inference_table_name} i
  LEFT JOIN {catalog}.{db}.{label_table_name} l
    ON i.application_id = l.application_id
       AND (i.transaction_ts = l.transaction_ts OR i.transaction_ts IS NULL)
  WHERE l.split = 'test'
  LIMIT 1000
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create monitor (Inference profile, classification)

# COMMAND ----------

try:
    info = w.quality_monitors.create(
        table_name=f"{catalog}.{db}.{inference_table_name}",
        inference_log=MonitorInferenceLog(
            problem_type=MonitorInferenceLogProblemType.PROBLEM_TYPE_CLASSIFICATION,
            prediction_col="prediction",
            timestamp_col="inference_timestamp",
            granularities=["1 day"],
            model_id_col="model_version",
            label_col="label_approved",
        ),
        schedule=MonitorCronSchedule(
            quartz_cron_expression="0 0 12 * * ?",
            timezone_id="America/Los_Angeles",
        ),
        assets_dir=f"{os.getcwd()}/monitoring",
        output_schema_name=f"{catalog}.{db}",
        baseline_table_name=f"{catalog}.{db}.{baseline_table_name}",
    )
    print(f"Created monitor for {catalog}.{db}.{inference_table_name}")
except Exception as e:
    if "already exist" in str(e).lower():
        info = w.quality_monitors.get(table_name=f"{catalog}.{db}.{inference_table_name}")
        print("Monitor already exists")
    else:
        raise e

# COMMAND ----------

while info.status == MonitorInfoStatus.MONITOR_STATUS_PENDING:
    info = w.quality_monitors.get(table_name=f"{catalog}.{db}.{inference_table_name}")
    time.sleep(10)
assert info.status == MonitorInfoStatus.MONITOR_STATUS_ACTIVE, "Monitor creation failed"

# COMMAND ----------

refreshes = w.quality_monitors.list_refreshes(table_name=f"{catalog}.{db}.{inference_table_name}").refreshes
if len(refreshes) == 0:
    w.quality_monitors.run_refresh(table_name=f"{catalog}.{db}.{inference_table_name}")
    time.sleep(5)
    refreshes = w.quality_monitors.list_refreshes(table_name=f"{catalog}.{db}.{inference_table_name}").refreshes
if refreshes:
    run_info = refreshes[0]
    while run_info.state in (MonitorRefreshInfoState.PENDING, MonitorRefreshInfoState.RUNNING):
        run_info = w.quality_monitors.get_refresh(
            table_name=f"{catalog}.{db}.{inference_table_name}", refresh_id=run_info.refresh_id
        )
        time.sleep(30)
    print("Refresh state:", run_info.state)

# COMMAND ----------

# MAGIC %md
# MAGIC View the monitoring dashboard in Catalog Explorer: open `{inference_table_name}` → **Quality** tab → **View dashboard**. Next: [08_drift_detection]($./08_drift_detection) to query drift metrics and trigger retrain.
