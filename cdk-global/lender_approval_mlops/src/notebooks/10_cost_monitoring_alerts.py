# Databricks notebook source
# MAGIC %md
# MAGIC # Cost Monitoring Alerts — System Tables
# MAGIC
# MAGIC Creates SQL alerts on `system.billing.usage` to monitor daily spend across:
# MAGIC - **Jobs** compute
# MAGIC - **Pipelines** (DLT/SDP)
# MAGIC - **Model Serving** endpoints
# MAGIC - **Vector Search** endpoints
# MAGIC - **Lakebase** (databases)
# MAGIC - **Notebooks** (interactive / all-purpose)
# MAGIC
# MAGIC Each alert fires when the previous day's spend exceeds a configurable threshold.
# MAGIC
# MAGIC Supports both **local development** (Databricks Connect / SDK) and **Databricks native** execution.

# COMMAND ----------

import os

def _is_databricks_runtime() -> bool:
    """Detect if running inside a Databricks cluster."""
    return "DATABRICKS_RUNTIME_VERSION" in os.environ

IS_DATABRICKS = _is_databricks_runtime()

if IS_DATABRICKS:
    dbutils.widgets.text("warehouse_id", "bce0a02b2be86f1b", "SQL Warehouse ID")
    dbutils.widgets.text("daily_threshold", "50000", "Daily Cost Threshold ($)")
    dbutils.widgets.text("jobs_threshold", "2000", "Jobs Cost Threshold ($)")
    dbutils.widgets.text("model_serving_threshold", "15000", "Model Serving Threshold ($)")
    dbutils.widgets.text("vector_search_threshold", "8000", "Vector Search Threshold ($)")
    dbutils.widgets.text("lakebase_threshold", "15000", "Lakebase Threshold ($)")
    dbutils.widgets.text("pipelines_threshold", "1000", "Pipelines Threshold ($)")
    dbutils.widgets.text("notebooks_threshold", "3000", "Notebooks Threshold ($)")

# COMMAND ----------

DEFAULTS = {
    "warehouse_id": "bce0a02b2be86f1b",
    "daily_threshold": "50000",
    "jobs_threshold": "2000",
    "model_serving_threshold": "15000",
    "vector_search_threshold": "8000",
    "lakebase_threshold": "15000",
    "pipelines_threshold": "1000",
    "notebooks_threshold": "3000",
}

def get_widget(name: str) -> str:
    """Get widget value from dbutils (Databricks) or fall back to defaults (local)."""
    if IS_DATABRICKS:
        return dbutils.widgets.get(name)
    return os.environ.get(f"ALERT_{name.upper()}", DEFAULTS[name])

warehouse_id = get_widget("warehouse_id")
daily_threshold = float(get_widget("daily_threshold"))
jobs_threshold = float(get_widget("jobs_threshold"))
model_serving_threshold = float(get_widget("model_serving_threshold"))
vector_search_threshold = float(get_widget("vector_search_threshold"))
lakebase_threshold = float(get_widget("lakebase_threshold"))
pipelines_threshold = float(get_widget("pipelines_threshold"))
notebooks_threshold = float(get_widget("notebooks_threshold"))

print(f"Running {'on Databricks' if IS_DATABRICKS else 'locally (Databricks Connect / SDK)'}")
print(f"Warehouse: {warehouse_id}")
print(f"Thresholds: daily=${daily_threshold:,.0f}, jobs=${jobs_threshold:,.0f}, "
      f"model_serving=${model_serving_threshold:,.0f}, vector_search=${vector_search_threshold:,.0f}, "
      f"lakebase=${lakebase_threshold:,.0f}, pipelines=${pipelines_threshold:,.0f}, "
      f"notebooks=${notebooks_threshold:,.0f}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Alert Query Definitions

# COMMAND ----------

import requests, json

if IS_DATABRICKS:
    host = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().get()
    token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
else:
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient(profile="group-demo")
    host = w.config.host.rstrip("/")
    token = w.config.authenticate()["Authorization"].removeprefix("Bearer ")

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def create_alert(display_name, query_text, column, op, threshold,
                  aggregation=None, empty_result_state="UNKNOWN",
                  quartz_cron="0 0 7 ? * * *", description=None):
    """Create a DBSQL alert via Alerts V2 API (POST /api/2.0/alerts).

    See: https://docs.databricks.com/api/workspace/alertsv2/createalert
    """
    payload = {
        "display_name": display_name,
        "query_text": query_text,
        "warehouse_id": warehouse_id,
        "evaluation": {
            "comparison_operator": op,
            "empty_result_state": empty_result_state,
            "source": {"name": column},
            "threshold": {"value": {"double_value": threshold}},
        },
        "schedule": {
            "quartz_cron_schedule": quartz_cron,
            "timezone_id": "America/New_York",
            "pause_status": "UNPAUSED",
        },
    }
    if aggregation:
        payload["evaluation"]["source"]["aggregation"] = aggregation
    if description:
        payload["custom_description"] = description
    resp = requests.post(f"{host}/api/2.0/alerts", headers=headers, json=payload)
    resp.raise_for_status()
    result = resp.json()
    alert_id = result.get("id")
    print(f"  Created alert: {display_name} (id: {alert_id})")
    return alert_id

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Daily Cost Summary Alert
# MAGIC Fires when total daily spend across all monitored categories exceeds threshold.

# COMMAND ----------

daily_summary_sql = """
SELECT
  ROUND(SUM(CASE WHEN billing_origin_product IN ('JOBS') THEN usage_quantity * COALESCE(p.pricing.default, 0) END), 2) AS jobs_cost,
  ROUND(SUM(CASE WHEN billing_origin_product IN ('DLT') THEN usage_quantity * COALESCE(p.pricing.default, 0) END), 2) AS pipelines_cost,
  ROUND(SUM(CASE WHEN billing_origin_product IN ('MODEL_SERVING') THEN usage_quantity * COALESCE(p.pricing.default, 0) END), 2) AS model_serving_cost,
  ROUND(SUM(CASE WHEN billing_origin_product IN ('VECTOR_SEARCH') THEN usage_quantity * COALESCE(p.pricing.default, 0) END), 2) AS vector_search_cost,
  ROUND(SUM(CASE WHEN billing_origin_product IN ('DATABASE', 'LAKEBASE') THEN usage_quantity * COALESCE(p.pricing.default, 0) END), 2) AS lakebase_cost,
  ROUND(SUM(CASE WHEN billing_origin_product IN ('ALL_PURPOSE', 'INTERACTIVE') THEN usage_quantity * COALESCE(p.pricing.default, 0) END), 2) AS notebooks_cost,
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS total_cost
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date = current_date() - 1
  AND billing_origin_product IN ('JOBS', 'DLT', 'MODEL_SERVING', 'VECTOR_SEARCH', 'DATABASE', 'LAKEBASE', 'ALL_PURPOSE', 'INTERACTIVE')
"""

print("Creating Daily Cost Summary...")
daily_alert_id = create_alert(
    "Alert: Daily Spend Exceeds Threshold",
    daily_summary_sql,
    "total_cost",
    "GREATER_THAN",
    daily_threshold,
    description="Yesterday's estimated cost across Jobs, Pipelines, Model Serving, Vector Search, Lakebase, and Notebooks.",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Model Serving Cost Alert
# MAGIC Fires when model serving + AI endpoint spend exceeds threshold.

# COMMAND ----------

model_serving_sql = """
SELECT
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS model_serving_cost,
  COUNT(DISTINCT usage_metadata.endpoint_name) AS active_endpoints
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date = current_date() - 1
  AND billing_origin_product = 'MODEL_SERVING'
"""

print("Creating Model Serving Alert...")
ms_alert_id = create_alert(
    "Alert: Model Serving Daily Spend",
    model_serving_sql,
    "model_serving_cost",
    "GREATER_THAN",
    model_serving_threshold,
    description="Yesterday's model serving endpoint cost with active endpoint count.",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Vector Search Cost Alert

# COMMAND ----------

vector_search_sql = """
SELECT
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS vector_search_cost,
  COUNT(DISTINCT usage_metadata.endpoint_name) AS active_endpoints
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date = current_date() - 1
  AND billing_origin_product = 'VECTOR_SEARCH'
"""

print("Creating Vector Search Alert...")
vs_alert_id = create_alert(
    "Alert: Vector Search Daily Spend",
    vector_search_sql,
    "vector_search_cost",
    "GREATER_THAN",
    vector_search_threshold,
    description="Yesterday's vector search endpoint cost.",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Lakebase Cost Alert

# COMMAND ----------

lakebase_sql = """
SELECT
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS lakebase_cost,
  COUNT(DISTINCT usage_metadata.database_instance_id) AS active_instances
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date = current_date() - 1
  AND billing_origin_product IN ('DATABASE', 'LAKEBASE')
"""

print("Creating Lakebase Alert...")
lb_alert_id = create_alert(
    "Alert: Lakebase Daily Spend",
    lakebase_sql,
    "lakebase_cost",
    "GREATER_THAN",
    lakebase_threshold,
    description="Yesterday's Lakebase (managed database) cost.",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Jobs Cost Alert

# COMMAND ----------

jobs_sql = """
SELECT
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS jobs_cost,
  COUNT(DISTINCT usage_metadata.job_id) AS active_jobs
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date = current_date() - 1
  AND billing_origin_product = 'JOBS'
"""

print("Creating Jobs Alert...")
jobs_alert_id = create_alert(
    "Alert: Jobs Daily Spend",
    jobs_sql,
    "jobs_cost",
    "GREATER_THAN",
    jobs_threshold,
    description="Yesterday's jobs compute cost with active job count.",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Pipelines (DLT) Cost Alert

# COMMAND ----------

pipelines_sql = """
SELECT
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS pipelines_cost,
  COUNT(DISTINCT usage_metadata.dlt_pipeline_id) AS active_pipelines
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date = current_date() - 1
  AND billing_origin_product = 'DLT'
"""

print("Creating Pipelines Alert...")
pl_alert_id = create_alert(
    "Alert: Pipelines Daily Spend",
    pipelines_sql,
    "pipelines_cost",
    "GREATER_THAN",
    pipelines_threshold,
    description="Yesterday's DLT/SDP pipeline cost with active pipeline count.",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Notebooks (Interactive) Cost Alert

# COMMAND ----------

notebooks_sql = """
SELECT
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS notebooks_cost,
  COUNT(DISTINCT COALESCE(usage_metadata.notebook_id, usage_metadata.cluster_id)) AS active_sessions
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date = current_date() - 1
  AND billing_origin_product IN ('ALL_PURPOSE', 'INTERACTIVE')
"""

print("Creating Notebooks Alert...")
nb_alert_id = create_alert(
    "Alert: Notebooks Daily Spend",
    notebooks_sql,
    "notebooks_cost",
    "GREATER_THAN",
    notebooks_threshold,
    description="Yesterday's interactive/all-purpose compute cost (notebooks, clusters).",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Top Spenders — Model Serving Endpoints (Informational Query)
# MAGIC This query surfaces the highest-cost endpoints for investigation. No alert — used for dashboards.

# COMMAND ----------

def run_sql_display(sql, title=""):
    """Run SQL and display results. Uses spark.sql on Databricks, SDK statement execution locally."""
    if title:
        print(f"\n{'='*60}\n{title}\n{'='*60}")
    if IS_DATABRICKS:
        spark.sql(sql).display()
    else:
        resp = requests.post(
            f"{host}/api/2.0/sql/statements",
            headers=headers,
            json={"statement": sql, "warehouse_id": warehouse_id, "wait_timeout": "50s"},
        )
        resp.raise_for_status()
        result = resp.json()
        columns = [c["name"] for c in result.get("manifest", {}).get("schema", {}).get("columns", [])]
        rows = [r for chunk in result.get("result", {}).get("data_array", []) for r in [chunk]]
        if not rows:
            print("  (no results)")
            return
        widths = [max(len(str(c)), max(len(str(r[i])) for r in rows)) for i, c in enumerate(columns)]
        header = " | ".join(c.ljust(w) for c, w in zip(columns, widths))
        print(header)
        print("-+-".join("-" * w for w in widths))
        for row in rows[:20]:
            print(" | ".join(str(v).ljust(w) for v, w in zip(row, widths)))
        if len(rows) > 20:
            print(f"  ... ({len(rows)} rows total)")

# COMMAND ----------

run_sql_display("""
SELECT
  usage_metadata.endpoint_name AS endpoint_name,
  billing_origin_product AS product,
  ROUND(SUM(usage_quantity), 2) AS total_dbus,
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS estimated_cost_usd
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date >= current_date() - 7
  AND billing_origin_product IN ('MODEL_SERVING', 'VECTOR_SEARCH')
  AND usage_metadata.endpoint_name IS NOT NULL
GROUP BY usage_metadata.endpoint_name, billing_origin_product
ORDER BY estimated_cost_usd DESC
LIMIT 15
""", "8. Top Spenders — Model Serving Endpoints")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Top Spenders — Jobs (Informational Query)

# COMMAND ----------

run_sql_display("""
SELECT
  usage_metadata.job_name AS job_name,
  usage_metadata.job_id AS job_id,
  ROUND(SUM(usage_quantity), 2) AS total_dbus,
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS estimated_cost_usd,
  COUNT(DISTINCT u.usage_date) AS active_days
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date >= current_date() - 7
  AND billing_origin_product = 'JOBS'
  AND usage_metadata.job_id IS NOT NULL
GROUP BY usage_metadata.job_name, usage_metadata.job_id
ORDER BY estimated_cost_usd DESC
LIMIT 15
""", "9. Top Spenders — Jobs")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. 7-Day Trend by Category (Informational Query)

# COMMAND ----------

run_sql_display("""
SELECT
  usage_date,
  CASE billing_origin_product
    WHEN 'JOBS' THEN 'Jobs'
    WHEN 'DLT' THEN 'Pipelines'
    WHEN 'MODEL_SERVING' THEN 'Model Serving'
    WHEN 'VECTOR_SEARCH' THEN 'Vector Search'
    WHEN 'DATABASE' THEN 'Lakebase'
    WHEN 'LAKEBASE' THEN 'Lakebase'
    WHEN 'ALL_PURPOSE' THEN 'Notebooks'
    WHEN 'INTERACTIVE' THEN 'Notebooks'
    ELSE billing_origin_product
  END AS cost_category,
  ROUND(SUM(usage_quantity), 2) AS total_dbus,
  ROUND(SUM(usage_quantity * COALESCE(p.pricing.default, 0)), 2) AS estimated_cost_usd
FROM system.billing.usage u
LEFT JOIN system.billing.list_prices p
  ON u.sku_name = p.sku_name AND u.cloud = p.cloud AND p.price_end_time IS NULL
WHERE u.usage_date >= current_date() - 7
  AND billing_origin_product IN ('JOBS', 'DLT', 'MODEL_SERVING', 'VECTOR_SEARCH', 'DATABASE', 'LAKEBASE', 'ALL_PURPOSE', 'INTERACTIVE')
GROUP BY usage_date, cost_category
ORDER BY usage_date DESC, estimated_cost_usd DESC
""", "10. 7-Day Trend by Category")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC | Alert | Trigger Column | Threshold | Schedule |
# MAGIC |-------|---------------|-----------|----------|
# MAGIC | Daily Spend Exceeds Threshold | `total_cost` | $50,000 | Daily 7am ET |
# MAGIC | Model Serving Daily Spend | `model_serving_cost` | $15,000 | Daily 7am ET |
# MAGIC | Vector Search Daily Spend | `vector_search_cost` | $8,000 | Daily 7am ET |
# MAGIC | Lakebase Daily Spend | `lakebase_cost` | $15,000 | Daily 7am ET |
# MAGIC | Jobs Daily Spend | `jobs_cost` | $2,000 | Daily 7am ET |
# MAGIC | Pipelines Daily Spend | `pipelines_cost` | $1,000 | Daily 7am ET |
# MAGIC | Notebooks Daily Spend | `notebooks_cost` | $3,000 | Daily 7am ET |
# MAGIC
# MAGIC All alerts query `system.billing.usage` joined with `system.billing.list_prices`
# MAGIC to convert DBUs into estimated USD costs. Thresholds are configurable via notebook widgets.
