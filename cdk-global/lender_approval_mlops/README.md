# Lender Approval MLOps – End-to-End Pipeline (MLOps Advanced)

Customer lender approval model using the **MLOps advanced** pattern: synthetic data → UC Volume → SDP (bronze/silver/gold) → Feature Store & label table → HPO training (Optuna) → Champion/Challenger validation & approval → batch inference with `fe.score_batch`, all managed via Databricks Asset Bundles.

## Components

1. **Synthetic data** – `src/generate_lender_data.py`  
   Generates loan applications (income, credit score, employment, DTI, etc.) and approval outcomes; writes parquet to UC Volume `raw_data/applications`.

2. **Spark Declarative Pipeline (SDP)** – `src/pipelines/lender_approval_etl/`  
   - **Bronze**: Ingest from Volume.  
   - **Silver**: Clean and validate.  
   - **Gold**: ML-ready table with train/test split and transaction_ts.

3. **MLOps advanced workflow** (notebooks, aligned with dbdemos 02-mlops-advanced)  
   - **01_feature_engineering**: Feature table + label table (no leakage), on-demand feature function `affordability_ratio`, table of application IDs for batch scoring.  
   - **02_model_training_hpo_optuna**: Feature lookups + feature function, `create_training_set`, preprocessors, Optuna HPO, `fe.log_model` with training set specs.  
   - **03b_from_notebook_to_models_in_uc**: Register best run to Unity Catalog, set Challenger alias.  
   - **04a_challenger_validation**: Validation checks (description, prediction, metric vs Champion), set tags including `Approval_Check=approved`.  
   - **04b_challenger_approval**: Check approval tag, set Champion alias.  
   - **05_batch_inference**: `fe.score_batch` with Champion model, save to offline inference table for monitoring.
   - **06_serve_features_and_model**: Online feature store (publish feature table) + Model Serving endpoint (Champion); optional smoke_test/drop_online_store widgets.
   - **07_model_monitoring**: Lakehouse Monitoring on unified inference table (offline + labels), baseline table, Inference profile (classification), schedule and refresh.
   - **08_drift_detection**: Refresh monitor, query profile/drift metrics, count violations, set task value `all_violations_count` for job branching (e.g. trigger retrain).

4. **Databricks Asset Bundle**  
   - `databricks.yml`: bundle name, variables (catalog, schema), targets (dev/prod).  
   - Resources: SDP pipeline + jobs for each step (generate data, pipeline run, feature engineering, training, register Challenger, validation, approval, batch inference, serve, monitoring, drift detection).

## Quick Start

```bash
cd lender_approval_mlops

# Validate
databricks bundle validate

# Deploy (dev)
databricks bundle deploy

# Run in order (MLOps advanced flow):
databricks bundle run lender_approval_mlops_generate_data
databricks bundle run lender_approval_mlops_pipeline_run
databricks bundle run lender_approval_mlops_feature_engineering_job
databricks bundle run lender_approval_mlops_training_job
databricks bundle run lender_approval_mlops_register_challenger_job
databricks bundle run lender_approval_mlops_validation_job
databricks bundle run lender_approval_mlops_approval_job
databricks bundle run lender_approval_mlops_inference_job
databricks bundle run lender_approval_mlops_serve_job
databricks bundle run lender_approval_mlops_monitoring_job
databricks bundle run lender_approval_mlops_drift_job
```

## Variables

Set in `databricks.yml` or per-target:

- `catalog` – Unity Catalog catalog.  
- `schema` – Schema for tables and volume.  
- `warehouse_id` – SQL warehouse for jobs/dashboards.  

Volume path for raw data: `/Volumes/{catalog}/{schema}/raw_data/applications/`.

## Skills Used

- **Synthetic data generation** – Faker, non-linear distributions, save to Volume.  
- **Spark Declarative Pipelines** – Bronze/silver/gold, serverless, Unity Catalog.  
- **Asset Bundles** – Multi-environment, pipeline + jobs + optional serving.
