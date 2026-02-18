# Databricks notebook source
# MAGIC %md
# MAGIC # Lender approval – real-time serving (MLOps advanced)
# MAGIC Deploy feature table to online store and the Champion model to a Model Serving endpoint for low-latency inference.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")
dbutils.widgets.text("model_version", "", "Model version (optional; default = Champion)")
dbutils.widgets.dropdown("drop_online_store", "False", ["True", "False"], "Reset Online Store")
dbutils.widgets.dropdown("smoke_test", "False", ["True", "False"], "Smoke test (skip create)")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

from databricks.feature_engineering import FeatureEngineeringClient
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, EndpointTag
from databricks.sdk.errors import ResourceDoesNotExist
from mlflow.tracking.client import MlflowClient
import time

fe = FeatureEngineeringClient()
w = WorkspaceClient()
client = MlflowClient(registry_uri="databricks-uc")
is_smoke_test = dbutils.widgets.get("smoke_test").lower() == "true"

model_version_param = dbutils.widgets.get("model_version").strip()
if model_version_param:
    model_version = model_version_param
else:
    model_version = client.get_model_version_by_alias(model_name, "Champion").version

print(f"Using model {model_name} version {model_version}, online store {online_store_name}, endpoint {endpoint_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Enable Change Data Feed on feature table (for online sync)

# COMMAND ----------

spark.sql(f"ALTER TABLE {catalog}.{db}.{feature_table_name} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create or get online store and publish feature table

# COMMAND ----------

online_store = fe.get_online_store(name=online_store_name)

if online_store:
    print(f"Online store exists: {online_store.name}, state: {online_store.state}")
    if dbutils.widgets.get("drop_online_store") == "True" and not is_smoke_test:
        fe.delete_online_store(name=online_store_name)
        time.sleep(60)
        online_store = fe.create_online_store(name=online_store_name, capacity="CU_1")
elif not is_smoke_test:
    print(f"Creating online store: {online_store_name}")
    online_store = fe.create_online_store(name=online_store_name, capacity="CU_1")

# COMMAND ----------

if not is_smoke_test and online_store:
    print("Publishing feature table to online store...")
    for retry in range(5):
        try:
            fe.publish_table(
                online_store=online_store,
                source_table_name=f"{catalog}.{db}.{feature_table_name}",
                online_table_name=f"{catalog}.{db}.{online_feature_table_name}",
            )
            break
        except Exception as e:
            if "feature sync is currently in progress" in str(e):
                time.sleep(10)
            else:
                raise e

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create or update Model Serving endpoint

# COMMAND ----------

served_entity_name = model_name.split(".")[-1]
endpoint_config = EndpointCoreConfigInput.from_dict({
    "served_entities": [{
        "entity_name": model_name,
        "entity_version": model_version,
        "scale_to_zero_enabled": True,
        "workload_size": "Small",
    }],
    "traffic_config": {
        "routes": [
            {"served_model_name": f"{served_entity_name}-{model_version}", "traffic_percentage": 100},
        ]
    },
    "auto_capture_config": {
        "catalog_name": catalog,
        "schema_name": db,
        "table_name_prefix": "lender_approval_served",
    },
})

if not is_smoke_test:
    try:
        w.serving_endpoints.update_config(
            name=endpoint_name,
            served_entities=endpoint_config.served_entities,
            traffic_config=endpoint_config.traffic_config,
        )
        print(f"Updated endpoint {endpoint_name}")
    except ResourceDoesNotExist:
        w.serving_endpoints.create(
            name=endpoint_name,
            config=endpoint_config,
            tags=[EndpointTag(key="project", value="lender_approval_mlops")],
        )
        print(f"Created endpoint {endpoint_name}")

# COMMAND ----------

if not is_smoke_test:
    from datetime import timedelta
    endpoint = w.serving_endpoints.wait_get_serving_endpoint_not_updating(endpoint_name, timeout=timedelta(minutes=30))
    assert endpoint.state.ready.value == "READY", "Endpoint not ready"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Test endpoint (example payload: application_id + transaction_ts for feature lookup)
# MAGIC The pyfunc wrapper returns structured JSON with the ML prediction,
# MAGIC deterministic rule checks, and a human-readable `decision_reason`.

# COMMAND ----------

import json

# Example: get rows from app_ids for payload
sample = spark.table(f"{catalog}.{db}.{app_ids_table_name}").limit(3).toPandas()
dataframe_records = sample.to_dict(orient="records") if len(sample) > 0 else [
    {"application_id": "APP-000001"},
]
print("Querying endpoint with:", dataframe_records)
response = w.serving_endpoints.query(name=endpoint_name, dataframe_records=dataframe_records)

# Pretty-print each prediction with reasoning
for i, pred in enumerate(response.predictions):
    print(f"\n{'='*60}")
    print(f"  Application:     {dataframe_records[i].get('application_id', 'N/A')}")
    if isinstance(pred, dict):
        print(f"  Final Decision:  {'APPROVED' if pred.get('prediction') == 1 else 'DENIED'}")
        print(f"  ML Prediction:   {'APPROVED' if pred.get('ml_prediction') == 1 else 'DENIED'}")
        print(f"  ML Probability:  {pred.get('ml_probability')}")
        print(f"  Income Check:    {pred.get('income_check')}")
        print(f"  ID Check:        {pred.get('id_check')}")
        print(f"  Reason:          {pred.get('decision_reason')}")
    else:
        print(f"  Prediction: {pred}")
print(f"\n{'='*60}")
