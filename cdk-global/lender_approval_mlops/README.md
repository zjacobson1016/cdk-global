# Lender Approval MLOps -- End-to-End Pipeline

Auto lending approval model using the **MLOps advanced** pattern on Databricks. Ingests three data sources (structured applications, pay stub PDFs, photo ID images), joins them in a medallion pipeline, trains a model with Optuna HPO, and applies deterministic business rules at prediction time with full decision reasoning.

---

## Business Value for CDK Global

CDK Global processes millions of auto loan applications annually across its dealer network. Manual underwriting, document verification, and fragmented data systems create friction, cost, and risk. This solution addresses those challenges directly.

### The Problem

| Challenge | Current State | Impact |
|---|---|---|
| **Manual document review** | Underwriters manually read pay stubs and check IDs for each application | 15-25 min per application; staff bottleneck at peak volume |
| **Income fraud exposure** | Self-reported income is taken at face value or spot-checked | 2-5% of funded loans have material income discrepancies (industry avg) |
| **Expired ID approvals** | ID expiration checks are manual and inconsistent | Compliance risk; potential regulatory penalties |
| **Siloed data** | Application data, supporting documents, and decisions live in separate systems | No unified view; difficult to audit or retrain models |
| **Slow model updates** | Models retrained quarterly at best; no automated drift detection | Model degrades as market conditions shift (rates, vehicle prices) |

### How This Solution Helps

**1. Automated Document Processing (ai_parse_document + ai_query)**

Pay stubs and photo IDs are automatically parsed and structured using Databricks AI Functions -- no manual data entry. Documents flow through the same pipeline as structured application data, joined on `application_id`.

> **Estimated savings**: Reducing manual document review from ~20 min to seconds per application. At 500K applications/year, that's ~166K hours of underwriter time redirected to complex cases.

**2. Deterministic Rules Catch What Models Miss**

The income validation rule automatically flags applications where verified pay-stub income diverges >30% from self-reported income. The ID expiration check prevents approvals with expired identification. These rules fire at both batch and real-time serving.

> **Estimated fraud reduction**: Catching even 1% of income-misrepresented loans on a $15B annual origination portfolio could prevent $30-50M in default losses. Expired-ID denials reduce compliance exposure.

**3. Unified Data Lakehouse Eliminates Silos**

All data -- structured applications, unstructured documents, model predictions, and decision reasoning -- lives in Unity Catalog. Every decision is auditable: was it the ML model, a rule override, or both?

> **Audit and compliance value**: Full lineage from raw document to final decision. Regulators can trace any approval/denial to its root cause. Reduces audit prep time by weeks.

**4. Continuous Monitoring and Automated Retraining**

Lakehouse Monitoring tracks prediction drift. When violations exceed a threshold, a retraining job triggers automatically -- no manual intervention. The Champion/Challenger pattern ensures new models are validated before promotion.

> **Model freshness**: Instead of quarterly retrains, the model stays current with market conditions. A 2-3% improvement in F1 from timely retraining translates to better approval targeting and fewer bad loans.

**5. Real-Time Decisioning at the Point of Sale**

The Model Serving endpoint returns sub-second decisions with full reasoning. Dealers get instant approvals with transparency -- why an application was approved or denied.

> **Dealer experience**: Faster decisions improve F&I throughput. A dealer processing 200 applications/month saves ~65 hours/month in wait time, improving customer satisfaction and close rates.

### Projected Annual Impact Summary

| Metric | Estimate |
|---|---|
| Underwriter hours saved | ~166,000 hrs/year (at 500K apps) |
| Fraud loss prevention | $30-50M/year (1% of $15B portfolio) |
| Compliance risk reduction | Full audit trail for every decision |
| Model accuracy improvement | 2-3% F1 lift from continuous retraining |
| Dealer decision latency | Minutes to seconds (real-time serving) |

*Estimates are illustrative and based on industry benchmarks for auto lending. Actual impact depends on CDK Global's application volumes, current processes, and portfolio composition.*

---

## Architecture

```
 Structured Data (parquet)          Unstructured Data (PDF + JPEG)
 ┌──────────────────────┐    ┌──────────────────┐  ┌──────────────────┐
 │ 01_generate_lender   │    │ 01_generate_      │  │ 01_generate_      │
 │ _data.py             │    │ lender_data_pdf.py│  │ lender_data_pdf.py│
 │ (applications)       │    │ (pay stubs)       │  │ (photo IDs)       │
 └──────┬───────────────┘    └──────┬─────────────┘  └──────┬────────────┘
        │                           │                        │
        ▼                           ▼                        ▼
  /raw_data/applications    /raw_data/pay_stubs      /raw_data/photo_ids
  (parquet)                 (PDF)                    (JPEG)
        │                           │                        │
 ───────┼───────────────────────────┼────────────────────────┼──── SDP Pipeline ──
        ▼                           ▼                        ▼
  bronze_applications         bronze_pay_stubs         bronze_photo_ids
  (Auto Loader parquet)       (ai_parse_document       (ai_parse_document
                               + ai_query)              + ai_query)
        │                           │                        │
        └───────────┬───────────────┘────────────────────────┘
                    ▼
            silver_applications
            (LEFT JOIN on application_id)
                    │
                    ▼
            gold_lender_features
            (income_verification_ratio, id_expired,
             name_match, doc_completeness, train/test split)
                    │
 ───────────────────┼──────────────────────────────────── ML Pipeline ──
                    ▼
          01_feature_engineering
          (Feature table, label table, on-demand UDFs:
           affordability_ratio, income_validation, id_expiration_check)
                    │
                    ▼
          02_model_training_hpo_optuna
          (Optuna HPO + pyfunc wrapper with deterministic rules)
                    │
                    ▼
          03b_register_challenger → 04a_validate → 04b_approve (Champion)
                    │
              ┌─────┴──────┐
              ▼            ▼
     05_batch_inference  06_serve_features_and_model
     (structured output  (real-time endpoint with
      + decision reason)  feature lookup + reasoning)
              │
              ▼
     07_monitoring → 08_drift_detection → (retrain loop)
```

## Data Sources

All three sources share `application_id` as the primary key for joining.

| Source | Format | Volume Path | Generator |
|---|---|---|---|
| Loan applications | Parquet | `raw_data/applications/` | `01_generate_lender_data.py` |
| Pay stubs | PDF | `raw_data/pay_stubs/` | `01_generate_lender_data_pdf.py` |
| Photo IDs | JPEG | `raw_data/photo_ids/` | `01_generate_lender_data_pdf.py` |

### Structured applications (parquet)
Income, credit score, employment years, debt-to-income, loan amount, loan purpose, and approval status. Generated with realistic non-linear distributions (lognormal income, beta DTI, exponential employment tenure).

### Pay stubs (PDF)
Earnings statements with employer info, gross/net pay, deductions breakdown, YTD totals. Includes a `Reference Number` field containing the `application_id`. Parsed in the pipeline using `ai_parse_document` + `ai_query` to extract verified income.

### Photo IDs (JPEG)
Driver's license-style images with name, DOB, address, license number, physical descriptors, issue/expiration dates. Parsed using `ai_parse_document` + `ai_query` to extract identity and expiration data.

## SDP Pipeline (Bronze / Silver / Gold)

| Table | Source | Key Fields |
|---|---|---|
| `bronze_applications` | Auto Loader (parquet) | application_id, income, credit_score, loan_amount, approved |
| `bronze_pay_stubs` | Auto Loader (binaryFile) + AI extraction | application_id, employer_name, gross_pay, ytd_gross |
| `bronze_photo_ids` | Auto Loader (binaryFile) + AI extraction | application_id, full_name, date_of_birth, license_number, expiration_date |
| `silver_applications` | LEFT JOIN all three on `application_id` | All application fields + verified income + identity fields |
| `gold_lender_features` | Derived features + train/test split | income_verification_ratio, id_expired, name_match, doc_completeness |

## ML Pipeline

### Feature Engineering (`01_feature_engineering`)
- Creates **Feature Table** (all gold columns) and **Label Table** (application_id, approved, split)
- Registers three **on-demand UC functions**:
  - `affordability_ratio(income, loan_amount)` -- loan-to-income ratio
  - `income_validation(income, verified_period_income)` -- 1=pass, 0=fail, -1=missing
  - `id_expiration_check(id_expiration_date)` -- 1=valid, 0=expired, -1=missing

### Training (`02_model_training_hpo_optuna`)
- Feature lookups + all three Feature Functions
- Optuna HPO across LogisticRegression, RandomForest, and LightGBM
- **Custom pyfunc wrapper** (`LenderApprovalWithRules`) that applies deterministic business rules at prediction time
- Logged with `fe.log_model(flavor=mlflow.pyfunc)` for FE-aware serving

### Deterministic Business Rules

Two hard rules override the ML prediction at both batch and serving time:

| Rule | Logic | Override |
|---|---|---|
| **Income validation** | Verified annual income (pay stub x26) must be 70%-150% of self-reported income | FAIL = auto-deny |
| **ID expiration** | Photo ID must not be expired | FAIL = auto-deny |

### Prediction Response Format

Every prediction (batch and real-time) returns structured output:

```json
{
  "prediction": 0,
  "ml_prediction": 1,
  "ml_probability": 0.8723,
  "income_check": "FAIL",
  "id_check": "PASS",
  "decision_reason": "DENIED by rules: Income mismatch (pay stub vs application)"
}
```

### Champion / Challenger Flow
- `03a` creates a deployment job for production promotion
- `03b` registers the best run as **Challenger** in Unity Catalog
- `04a` validates (description, predictions, metric comparison vs Champion)
- `04b` promotes to **Champion** if approval tag is set

### Batch Inference (`05_batch_inference`)
- Loads pyfunc model via `mlflow.pyfunc.load_model` (FE wrapper handles feature lookup)
- Returns structured predictions with reasoning
- Saves to offline inference table for monitoring

### Real-Time Serving (`06_serve_features_and_model`)
- Publishes feature table to online store
- Deploys Champion model to Model Serving endpoint
- Feature Functions evaluated on-demand at serving time
- Returns structured JSON with `decision_reason`

### Monitoring & Drift (`07`, `08`)
- Lakehouse Monitoring on unified inference table
- Drift detection with violation counting
- Conditional retrain trigger via job branching

## Agent Bricks -- Multi-Agent Supervisor

The pipeline feeds into a three-agent architecture orchestrated by a **CDK Lending Supervisor** (Multi-Agent Supervisor). See the [top-level README](../README.md) for full details.

| Agent | Type | Purpose |
|---|---|---|
| **Lender Approval** | Model Serving Endpoint | ML + rules-based loan approval with structured reasoning |
| **Lending Analytics** | Genie Space | Self-service SQL analytics on gold + inference tables |
| **Lender Shopping** | Custom Agent (ResponsesAgent) | UC function `shop_lenders` for multi-lender rate comparison |

### Lender Shopping UC Function

`shop_lenders(credit_score, income, loan_amount, term, vehicle_year)` queries the `lender_programs` table (8 lenders, 20 programs) and returns matching programs sorted by APR with estimated monthly payments and approval likelihood.

### Setup notebooks

| Notebook | Purpose |
|---|---|
| `09a_generate_lender_programs` | Creates `lender_programs` table and `shop_lenders` UC function |
| `09b_setup_agent_bricks` | Deploys Lender Shopping Agent, creates Genie Space, creates MAS |

### Agent source code

| File | Description |
|---|---|
| `src/agent/agent.py` | ResponsesAgent with LangGraph + UCFunctionToolkit (`shop_lenders`, `affordability_ratio`) |
| `src/agent/test_agent.py` | Test with prime and subprime borrower scenarios |
| `src/agent/log_model.py` | Log and register agent model in Unity Catalog |

## Quick Start

```bash
cd cdk-global/lender_approval_mlops

# Deploy bundle
databricks bundle validate
databricks bundle deploy -t dev

# 1. Generate structured application data (parquet)
databricks bundle run generate_lender_data -t dev

# 2. Generate supporting documents (pay stubs + photo IDs)
databricks bundle run generate_supporting_docs -t dev

# 3. Run the full MLOps job (pipeline + training + inference + monitoring)
databricks bundle run lender_approval_mlops -t dev

# 4. Generate lender programs data + shop_lenders UC function
#    Run notebook: 09a_generate_lender_programs

# 5. Set up Agent Bricks (Genie Space + Lender Shopping Agent + MAS)
#    Run notebook: 09b_setup_agent_bricks
#    Or use MCP tools (see top-level README)
```

## Project Structure

```
lender_approval_mlops/
  databricks.yml                          # Bundle config (variables, targets)
  resources/
    lender_approval_mlops_pipeline.yml    # SDP pipeline definition
    lender_approval_mlops_job.yml         # Job definitions (end-to-end + retrain)
  src/
    requirements.txt                      # Python dependencies
    agent/
      agent.py                            # Lender Shopping Agent (ResponsesAgent + LangGraph)
      test_agent.py                       # Agent test script
      log_model.py                        # MLflow model logging + UC registration
    notebooks/
      _setup_lender.py                    # Shared config (catalog, schema, table names)
      01_generate_lender_data.py          # Generate structured parquet applications
      01_generate_lender_data_pdf.py      # Generate pay stub PDFs + photo ID JPEGs
      01_feature_engineering.py           # Feature table, labels, UC functions
      02_model_training_hpo_optuna.py     # Optuna HPO + pyfunc wrapper with rules
      03a_create_deployment_job.py        # Create deployment job
      03b_from_notebook_to_models_in_uc.py # Register Challenger
      04a_challenger_validation.py        # Validate Challenger
      04b_challenger_approval.py          # Promote to Champion
      05_batch_inference.py               # Batch predictions with reasoning
      06_serve_features_and_model.py      # Online store + serving endpoint
      07_model_monitoring.py              # Lakehouse Monitoring setup
      08_drift_detection.py               # Drift detection + violation count
      09a_generate_lender_programs.py     # Lender programs data + shop_lenders UC fn
      09b_setup_agent_bricks.py           # Genie Space + agent deploy + MAS setup
    pipelines/lender_approval_etl/
      transformations/
        bronze_applications.py            # Auto Loader (parquet)
        bronze_pay_stubs.py               # ai_parse_document (PDF)
        bronze_photo_ids.py               # ai_parse_document (JPEG)
        silver_applications.py            # 3-way join on application_id
        gold_features.py                  # ML features + verification signals
```

## Configuration

Set in `databricks.yml` or per-target override:

| Variable | Description | Default |
|---|---|---|
| `catalog` | Unity Catalog catalog | `mfg_mc_se_sa` |
| `schema` | Schema for tables and volume | `cdk` |
| `warehouse_id` | SQL warehouse for jobs | `bce0a02b2be86f1b` |

Volume paths:
- `/Volumes/{catalog}/{schema}/raw_data/applications/` -- structured parquet
- `/Volumes/{catalog}/{schema}/raw_data/pay_stubs/` -- pay stub PDFs
- `/Volumes/{catalog}/{schema}/raw_data/photo_ids/` -- photo ID JPEGs

## Dependencies

```
faker>=22.0.0        # Synthetic data generation
fpdf2>=2.8.0         # Pay stub PDF creation
Pillow>=10.0.0       # Photo ID JPEG creation
lightgbm             # Model training
optuna               # Hyperparameter optimization
databricks-feature-engineering>=0.13.0a8
databricks-sdk>=0.68.0
mlflow-skinny>=3.6.0
databricks-langchain           # UC Function tools for agent
langgraph>=0.3.4               # Agent graph framework
databricks-agents              # Agent deployment
```
