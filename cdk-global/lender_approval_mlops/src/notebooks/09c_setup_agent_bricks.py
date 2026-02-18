# Databricks notebook source
# MAGIC %md
# MAGIC # Setup Agent Bricks — Genie Space, UC Function Wrappers & MAS
# MAGIC
# MAGIC Creates the conversational AI layer for the CDK lending platform:
# MAGIC 1. **UC Function**: `predict_loan_approval` — wraps the ML model serving endpoint
# MAGIC 2. **Genie Space**: CDK Lending Analytics — natural language SQL over gold tables
# MAGIC 3. **MAS**: CDK Lending Supervisor — multi-agent orchestration (Genie + model + lender shopping)
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - `gold_lender_features` materialized view (via SDP pipeline)
# MAGIC - `lender_programs` table (via notebook 09a)
# MAGIC - `shop_lenders` UC function (via notebook 09a)
# MAGIC - `lender_approval_serving_cdk` model serving endpoint (via notebook 06)

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create `predict_loan_approval` UC Function
# MAGIC Wraps the model serving endpoint using `ai_query()` so it can be called
# MAGIC as a UC function tool in agents, Genie Spaces, and MAS sub-agents.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {catalog}.{schema}.predict_loan_approval(
  application_id_in STRING
)
RETURNS STRUCT<prediction INT, ml_prediction INT, ml_probability DOUBLE, income_check STRING, id_check STRING, decision_reason STRING>
LANGUAGE SQL
COMMENT 'Score a loan application through the real-time ML model serving endpoint ({endpoint_name}). Pass an application ID (e.g. APP-003249) and receive the approval decision with prediction, ml_probability, income_check, id_check, and decision_reason.'
RETURN
  SELECT ai_query(
    '{endpoint_name}',
    NAMED_STRUCT('application_id', application_id_in),
    returnType => 'STRUCT<prediction INT, ml_prediction INT, ml_probability DOUBLE, income_check STRING, id_check STRING, decision_reason STRING>'
  )
""")

print(f"Created UC function: {catalog}.{schema}.predict_loan_approval")
print(f"  Wraps endpoint: {endpoint_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Create Genie Space
# MAGIC Uses the Databricks SDK to create a Genie Space with the gold tables,
# MAGIC lender programs, and inference tables.

# COMMAND ----------

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.dashboards import GenieSpace, GenieTableIdentifier, GenieCuratedQuestion

w = WorkspaceClient()

table_ids = [
    GenieTableIdentifier(table_identifier=f"{catalog}.{schema}.gold_lender_features"),
    GenieTableIdentifier(table_identifier=f"{catalog}.{schema}.lender_programs"),
    GenieTableIdentifier(table_identifier=f"{catalog}.{schema}.lender_approval_inference_table"),
    GenieTableIdentifier(table_identifier=f"{catalog}.{schema}.lender_approval_offline_inference"),
    GenieTableIdentifier(table_identifier=f"{catalog}.{schema}.lending_analytics_metrics"),
]

sample_questions = [
    GenieCuratedQuestion(question="What is the approval rate by credit tier?"),
    GenieCuratedQuestion(question="Which loan purposes have the highest average loan amount?"),
    GenieCuratedQuestion(question="Show me lender programs available for a borrower with credit score 680 and income over $30K"),
    GenieCuratedQuestion(question="What percentage of applications have full document verification (pay stub + photo ID)?"),
    GenieCuratedQuestion(question="Compare approval rates between applicants with and without pay stubs"),
    GenieCuratedQuestion(question="Which lenders offer the lowest APR for prime borrowers?"),
    GenieCuratedQuestion(question="What is the average debt-to-income ratio for approved vs denied applications?"),
    GenieCuratedQuestion(question="Show monthly application volume trends"),
    GenieCuratedQuestion(question="How many lender programs accept credit scores below 600?"),
    GenieCuratedQuestion(question="What is the model prediction breakdown from the latest batch inference?"),
]

genie_space = w.genie.create(
    space_id=None,
    display_name="CDK Lending Analytics",
    description=(
        "Explore CDK Global's auto lending pipeline data. Ask questions about "
        "loan applications, approval rates, borrower profiles, credit tiers, "
        "document verification, lender programs, and model inference results. "
        "Powered by the gold_lender_features table (15K applications), "
        "lender_programs (20 programs from 8 lenders), inference tables, "
        "and the lending_analytics_metrics metric view with governed KPIs "
        "(12 dimensions, 17 measures) for standardized business analytics."
    ),
    table_identifiers=table_ids,
    curated_questions=sample_questions,
    warehouse_id=warehouse_id,
)

genie_space_id = genie_space.space_id
print(f"Created Genie Space: {genie_space.display_name}")
print(f"  Space ID: {genie_space_id}")
print(f"  Tables:   {len(table_ids)}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Create Multi-Agent Supervisor (MAS)
# MAGIC Orchestrates three agents:
# MAGIC - **lending_analytics** (Genie) — data exploration and analytics
# MAGIC - **loan_approval** (UC Function) — real-time ML scoring via `predict_loan_approval`
# MAGIC - **lender_shopping** (UC Function) — lender rate comparison via `shop_lenders`

# COMMAND ----------

import requests

host = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().get()
token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

mas_payload = {
    "name": "CDK Lending Supervisor",
    "description": (
        "CDK Global's multi-agent lending supervisor. Routes dealer and F&I "
        "manager queries to specialized agents: analytics for data questions, "
        "loan approval for scoring applications, and lender shopping for rate comparisons."
    ),
    "instructions": (
        "Route queries as follows:\n"
        "- Questions about trends, volumes, rates, averages, comparisons, or data exploration → lending_analytics agent\n"
        "- Questions about scoring or approving a specific application (with an application ID like APP-XXXXX) → loan_approval agent\n"
        "- Questions about finding the best lender rates, shopping programs, or comparing offers for a borrower profile → lender_shopping agent"
    ),
    "agents": [
        {
            "name": "lending_analytics",
            "description": "Answers data analytics questions about the auto lending pipeline — approval rates, volumes, credit tiers, document verification, and trends.",
            "agent_type": "genie",
            "genie_space": {"id": genie_space_id},
        },
        {
            "name": "loan_approval",
            "description": "Scores a specific loan application for real-time approval using the ML model. Pass an application ID (e.g. APP-003249) to get the approval decision.",
            "agent_type": "unity_catalog_function",
            "unity_catalog_function": {
                "uc_path": {
                    "catalog": catalog,
                    "schema": schema,
                    "name": "predict_loan_approval",
                }
            },
        },
        {
            "name": "lender_shopping",
            "description": "Shops across lender programs to find the best rates for a borrower profile. Provide credit score, income, loan amount, term, and vehicle year.",
            "agent_type": "unity_catalog_function",
            "unity_catalog_function": {
                "uc_path": {
                    "catalog": catalog,
                    "schema": schema,
                    "name": "shop_lenders",
                }
            },
        },
    ],
}

resp = requests.post(
    f"{host}/api/2.0/multi-agent-supervisors",
    headers={"Authorization": f"Bearer {token}"},
    json=mas_payload,
)
resp.raise_for_status()
mas_result = resp.json()

tile_id = mas_result["multi_agent_supervisor"]["tile"]["tile_id"]
print(f"Created MAS: CDK Lending Supervisor")
print(f"  Tile ID: {tile_id}")
print(f"  Agents:  {len(mas_result['multi_agent_supervisor']['agents'])}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC | Component | Type | Status |
# MAGIC |-----------|------|--------|
# MAGIC | `predict_loan_approval` | UC Function | **Created** — wraps `lender_approval_serving_cdk` via `ai_query()` |
# MAGIC | `shop_lenders` | UC Function | **Created** (notebook 09a) — lender program matching |
# MAGIC | CDK Lending Analytics | Genie Space | **Created** — 5 tables (incl. metric view), 10 sample questions |
# MAGIC | CDK Lending Supervisor | MAS | **Created** — 3 agents (Genie + 2 UC functions) |
