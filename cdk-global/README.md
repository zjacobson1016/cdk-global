# CDK Global -- Databricks Solution Accelerator

End-to-end auto lending solution on Databricks for CDK Global. Combines MLOps, document AI, deterministic business rules, and a multi-agent conversational interface for dealership F&I (Finance & Insurance) managers.

---

## Solution Overview

```
                           ┌──────────────────────────────────┐
                           │    CDK Lending Supervisor (MAS)   │
                           │  Unified conversational interface │
                           └──────────┬───────────┬───────────┘
                                      │           │
                ┌─────────────────────┼───────────┼─────────────────────┐
                │                     │           │                     │
                ▼                     ▼           ▼                     │
  ┌─────────────────────┐ ┌──────────────────┐ ┌──────────────────────┐│
  │ Lender Approval     │ │ Lending Analytics│ │ Lender Shopping      ││
  │ Agent               │ │ Genie Space      │ │ Agent                ││
  │                     │ │                  │ │                      ││
  │ ML model + rules    │ │ Self-service SQL │ │ UC Function tool:    ││
  │ Income verification │ │ on gold layer +  │ │ shop_lenders()       ││
  │ ID expiration check │ │ inference tables │ │ Multi-lender rate    ││
  │ Decision reasoning  │ │                  │ │ comparison           ││
  └─────────────────────┘ └──────────────────┘ └──────────────────────┘│
  Model Serving Endpoint   Genie Space (SQL)   Custom Agent Endpoint   │
  ──────────────────────────────────────────────────────────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           │                          │                          │
           ▼                          ▼                          ▼
  ┌──────────────────┐    ┌────────────────────┐    ┌──────────────────┐
  │ MLOps Pipeline   │    │ SDP Medallion      │    │ Lender Programs  │
  │ (training, HPO,  │    │ Pipeline (bronze/  │    │ Reference Data   │
  │  monitoring)     │    │  silver/gold)      │    │ (8 lenders,      │
  └──────────────────┘    └────────────────────┘    │  20 programs)    │
                                                    └──────────────────┘
```

---

## Projects

| Project | Description | Details |
|---|---|---|
| **lender_approval_mlops/** | End-to-end MLOps pipeline: data generation, document AI, SDP, model training, deterministic rules, serving, monitoring | [README](lender_approval_mlops/README.md) |

---

## Multi-Agent Supervisor (MAS)

The **CDK Lending Supervisor** is a Multi-Agent Supervisor that provides a single conversational interface for dealership F&I managers. It routes questions to three specialized agents automatically.

### Agent 1: Lender Approval Agent

**Type:** Model Serving Endpoint (`lender_approval_serving_cdk`)

Evaluates loan applications using a trained ML model combined with two deterministic business rules:

| Rule | Logic | Override |
|---|---|---|
| **Income validation** | Verified annual income (pay stub x26) must be 70%-150% of self-reported | FAIL = auto-deny |
| **ID expiration** | Photo ID must not be expired | FAIL = auto-deny |

Every response includes structured reasoning:

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

**Example questions routed here:**
- "Should I approve this application? Credit 680, income $52K, loan $28K"
- "Evaluate this borrower: 740 credit, $85K income, $45K loan on a 2025 Tahoe"

### Agent 2: Lending Analytics Genie Space

**Type:** Genie Space (natural language to SQL)

Connected to gold-layer and inference tables for self-service analytics. Dealers and analysts can ask questions in plain English and get instant data-driven answers.

**Tables included:**

| Table | Description |
|---|---|
| `gold_lender_features` | ML-ready features with verification signals |
| `lender_approval_inference_table` | Predictions + labels for monitoring |
| `lender_approval_offline_inference` | Batch predictions with decision reasoning |
| `lender_programs` | Lender program reference data (rates, terms, criteria) |
| `lender_approval_feature_table` | Feature store with point-in-time lookup |

**Example questions routed here:**
- "What is the overall approval rate this month?"
- "How many applications were denied by deterministic rules vs the ML model?"
- "Show the top 5 lenders by lowest average APR for prime borrowers"
- "What percentage of applications have income verification mismatches?"
- "Compare approval rates by credit score tier"
- "Show me denied applications where the ML model would have approved"

### Agent 3: Lender Shopping Agent

**Type:** Custom Agent Endpoint (ResponsesAgent + LangGraph + UC Function tools)

Helps F&I managers find the best lending programs for their customers by comparing rates across multiple lenders in real time.

**UC Function: `shop_lenders`**

```sql
shop_lenders(
  credit_score_in     INT,      -- borrower credit score
  annual_income_in    DOUBLE,   -- annual gross income
  loan_amount_in      DOUBLE,   -- requested loan amount
  loan_term_months_in INT,      -- desired term in months
  vehicle_year_in     INT       -- vehicle model year
)
RETURNS TABLE(
  lender_name, program_name, apr, max_apr,
  estimated_monthly_payment, max_ltv, approval_likelihood
)
```

The function queries the `lender_programs` table (8 lenders, 20 programs) and returns matching programs sorted by best APR, with:
- **Estimated monthly payment** calculated using amortization formula
- **Approval likelihood** (HIGH / MEDIUM / LOW) based on how far the borrower exceeds minimum requirements

**Lenders in the system:**

| Lender | Programs | Credit Range |
|---|---|---|
| TD Auto Finance | Tier 1 New, Tier 2 CPO | 680-740+ |
| Chase Auto | Preferred New, Standard Used | 660-720+ |
| Ally Financial | SmartAuto New/Used, Subprime Recovery | 520-680+ |
| Capital One Auto Finance | Prime New/Used, Near Prime | 600-700+ |
| Wells Fargo Dealer Services | Prime Auto, Non-Prime | 580-700+ |
| Navy Federal Credit Union | New Auto, Used Auto | 640-670+ |
| AmeriCredit (GM Financial) | GM Loyalty New, Standard Used | 550-620+ |
| Westlake Financial Services | Deep Subprime, Second Chance | 450-500+ |

**Example questions routed here:**
- "Find me the best rates for a customer with 740 credit, $72K income, $38K loan on a 2025 Honda"
- "What lenders accept credit scores below 550?"
- "Compare Ally vs Chase rates for a $40K new car loan"
- "My customer has a 580 score and needs a $15K used car loan. What are the options?"
- "What's the cheapest monthly payment for a $25K loan over 60 months with 680 credit?"

### MAS Routing Logic

```
User question
    │
    ▼
┌─────────────────────────────────────────┐
│           CDK Lending Supervisor         │
│                                         │
│  Approval/deny decision?                │
│    → lender_approval agent              │
│                                         │
│  Data, metrics, trends, reports?        │
│    → lending_analytics (Genie Space)    │
│                                         │
│  Rate comparison, lender programs,      │
│  monthly payments?                      │
│    → lender_shopping agent              │
└─────────────────────────────────────────┘
```

### Creating the MAS

Use MCP tools to create each component:

```bash
# 1. Create the Genie Space (self-service analytics)
create_or_update_genie(
    display_name="CDK Lending Analytics",
    table_identifiers=[
        "mfg_mc_se_sa.cdk.gold_lender_features",
        "mfg_mc_se_sa.cdk.lender_approval_inference_table",
        "mfg_mc_se_sa.cdk.lender_approval_offline_inference",
        "mfg_mc_se_sa.cdk.lender_programs",
        "mfg_mc_se_sa.cdk.lender_approval_feature_table"
    ],
    description="Self-service analytics for CDK Global auto lending",
    sample_questions=[
        "What is the overall approval rate this month?",
        "How many applications were denied by rules vs ML model?",
        "Show top lenders by lowest APR for prime borrowers"
    ]
)

# 2. Deploy the Lender Shopping Agent (after running 09a + log_model.py)
#    The endpoint is created automatically by agents.deploy()

# 3. Create the Multi-Agent Supervisor
create_or_update_mas(
    name="CDK Lending Supervisor",
    agents=[
        {
            "name": "lender_approval",
            "endpoint_name": "lender_approval_serving_cdk",
            "description": "Evaluates loan applications. Returns approval/denial with reasoning using ML model + deterministic rules (income verification, ID expiration)."
        },
        {
            "name": "lending_analytics",
            "genie_space_id": "<GENIE_SPACE_ID>",
            "description": "Answers data and analytics questions about lending performance using SQL. Covers approval rates, rule overrides, credit distributions, loan metrics."
        },
        {
            "name": "lender_shopping",
            "endpoint_name": "lender_shopping_agent_cdk",
            "description": "Compares auto loan programs from multiple lenders. Takes borrower profile (credit, income, loan amount, term, vehicle year) and returns matching rates, payments, and approval likelihood."
        }
    ],
    description="Unified lending assistant for CDK Global dealership F&I managers.",
    instructions="Route approval questions to lender_approval, data/metrics questions to lending_analytics, rate/program comparisons to lender_shopping."
)
```

---

---

## Breakout Sessions

Three hands-on breakout sessions that walk through the full solution end-to-end. Each session is self-contained and maps to specific notebooks in the project.

### Session 1: Data Engineering -- Data Pipelines

| | |
|---|---|
| **Focus** | Ingesting structured and unstructured data through a medallion architecture |
| **Notebooks** | `01_generate_lender_data`, `01_generate_lender_data_pdf`, SDP pipeline |
| **Duration** | 60 min |

**Topics covered:**
- Generating synthetic structured data (parquet) and unstructured documents (pay stub PDFs, photo ID JPEGs)
- Unity Catalog Volumes for raw data storage
- Auto Loader for incremental ingestion (parquet + binaryFile formats)
- Databricks AI Functions (`ai_parse_document`, `ai_query`) for document extraction
- Spark Declarative Pipeline (SDP) with Bronze / Silver / Gold layers
- Three-way `LEFT JOIN` on `application_id` to unify all data sources
- Derived features: `income_verification_ratio`, `id_expired`, `name_match`, `doc_completeness`

**Key takeaway:** A single pipeline ingests structured applications, pay stub PDFs, and photo ID images -- joining them into ML-ready features with zero manual data entry.

---

### Session 2: Machine Learning & MLOps

| | |
|---|---|
| **Focus** | Feature engineering, model training with business rules, and production deployment |
| **Notebooks** | `01_feature_engineering` through `08_drift_detection` |
| **Duration** | 75 min |

**Topics covered:**
- Feature Engineering with on-demand UC functions (`affordability_ratio`, `income_validation`, `id_expiration_check`)
- Optuna hyperparameter optimization across LogisticRegression, RandomForest, and LightGBM
- Custom `mlflow.pyfunc.PythonModel` wrapper that applies deterministic business rules at prediction time
- Structured prediction output with `decision_reason` for every approval/denial
- Champion / Challenger model promotion workflow
- Batch inference via `fe.score_batch` with rule override reasoning
- Real-time Model Serving endpoint with feature lookup + Feature Functions
- Lakehouse Monitoring for drift detection with automated retrain triggers

**Key takeaway:** The ML model and deterministic rules (income verification, ID expiration) are packaged together so every prediction -- batch or real-time -- returns a transparent decision with full reasoning.

---

### Session 3: AI -- Agent Bricks & Conversational AI

| | |
|---|---|
| **Focus** | Building a multi-agent conversational interface for dealership F&I managers |
| **Notebooks** | `09a_generate_lender_programs`, `09b_setup_agent_bricks`, `src/agent/` |
| **Duration** | 60 min |

**Topics covered:**
- Lender programs reference data and the `shop_lenders` UC Function
- Building a custom agent with ResponsesAgent + LangGraph + UCFunctionToolkit
- Deploying the Lender Shopping Agent to a Model Serving endpoint
- Creating a Genie Space for self-service SQL analytics on gold + inference tables
- Configuring the Multi-Agent Supervisor (MAS) to orchestrate all three agents
- Routing logic: approval decisions vs. analytics queries vs. rate shopping
- Testing the unified conversational interface end-to-end

**Key takeaway:** A single chat interface lets F&I managers approve loans, explore lending data, and shop lender rates -- all routed automatically to the right specialist agent.

---

### Schedule Overview

```
 Time          Session                                     Track
 ─────────────────────────────────────────────────────────────────
 9:00 - 9:15   Welcome & Solution Overview                 All
 ─────────────────────────────────────────────────────────────────
 9:15 - 10:15  Session 1: Data Engineering                 Data Pipelines
               Auto Loader, Document AI, SDP Pipeline
               Bronze / Silver / Gold medallion
 ─────────────────────────────────────────────────────────────────
 10:15 - 10:30 Break
 ─────────────────────────────────────────────────────────────────
 10:30 - 11:45 Session 2: Machine Learning & MLOps         ML / MLOps
               Feature Engineering, Optuna HPO,
               Business Rules, Champion/Challenger,
               Serving, Monitoring & Drift
 ─────────────────────────────────────────────────────────────────
 11:45 - 12:00 Break
 ─────────────────────────────────────────────────────────────────
 12:00 - 1:00  Session 3: AI & Agent Bricks                AI
               Lender Shopping Agent, Genie Space,
               Multi-Agent Supervisor, UC Functions
 ─────────────────────────────────────────────────────────────────
 1:00 - 1:30   Wrap-up & Next Steps                        All
 ─────────────────────────────────────────────────────────────────
```

---

## Quick Start

```bash
cd cdk-global/lender_approval_mlops

# Deploy the Databricks Asset Bundle
databricks bundle validate
databricks bundle deploy -t dev

# 1. Generate structured application data (parquet)
databricks bundle run generate_lender_data -t dev

# 2. Generate supporting documents (pay stubs + photo IDs)
databricks bundle run generate_supporting_docs -t dev

# 3. Run the full MLOps job (pipeline + training + inference + monitoring)
databricks bundle run lender_approval_mlops -t dev

# 4. Generate lender programs reference data + shop_lenders UC function
#    Run notebook: 09a_generate_lender_programs

# 5. Set up Agent Bricks (Genie Space + Lender Shopping Agent + MAS)
#    Run notebook: 09b_setup_agent_bricks
#    Or use MCP tools as shown above
```

---

## Architecture Summary

| Layer | Component | Technology |
|---|---|---|
| **Data Ingestion** | Structured apps + pay stubs + photo IDs | Auto Loader, ai_parse_document, ai_query |
| **Data Pipeline** | Bronze / Silver / Gold medallion | Spark Declarative Pipeline (SDP) |
| **Feature Store** | Feature table + on-demand UC functions | Databricks Feature Engineering |
| **ML Training** | Optuna HPO + pyfunc wrapper with rules | MLflow, scikit-learn, LightGBM |
| **Batch Inference** | fe.score_batch + structured output | MLflow pyfunc, Feature Engineering |
| **Real-Time Serving** | Model endpoint + feature lookup | Model Serving, Online Store |
| **Monitoring** | Drift detection + auto-retrain trigger | Lakehouse Monitoring |
| **Analytics** | Self-service SQL on lending data | Genie Space |
| **Rate Shopping** | Multi-lender comparison via UC function | ResponsesAgent + LangGraph + UC Functions |
| **Orchestration** | Unified conversational interface | Multi-Agent Supervisor (MAS) |

---

## Project Structure

```
cdk-global/
  README.md                                    ← this file
  lender_approval_mlops/
    README.md                                  # Detailed MLOps pipeline documentation
    databricks.yml                             # Databricks Asset Bundle config
    resources/
      lender_approval_mlops_pipeline.yml       # SDP pipeline definition
      lender_approval_mlops_job.yml            # Job definitions
    src/
      requirements.txt                         # Python dependencies
      agent/
        agent.py                               # Lender Shopping Agent (ResponsesAgent)
        test_agent.py                          # Agent test script
        log_model.py                           # MLflow model logging
      notebooks/
        _setup_lender.py                       # Shared config
        01_generate_lender_data.py             # Structured parquet generation
        01_generate_lender_data_pdf.py         # Pay stub PDFs + photo ID JPEGs
        01_feature_engineering.py              # Feature table + UC functions
        02_model_training_hpo_optuna.py        # Optuna HPO + pyfunc wrapper
        03a_create_deployment_job.py           # Deployment job creation
        03b_from_notebook_to_models_in_uc.py   # Register Challenger
        04a_challenger_validation.py           # Validate Challenger
        04b_challenger_approval.py             # Promote to Champion
        05_batch_inference.py                  # Batch predictions with reasoning
        06_serve_features_and_model.py         # Online store + serving endpoint
        07_model_monitoring.py                 # Lakehouse Monitoring
        08_drift_detection.py                  # Drift detection + retrain trigger
        09a_generate_lender_programs.py        # Lender programs data + shop_lenders UC fn
        09b_setup_agent_bricks.py              # Genie Space + agent deploy + MAS setup
      pipelines/lender_approval_etl/
        transformations/
          bronze_applications.py               # Auto Loader (parquet)
          bronze_pay_stubs.py                  # ai_parse_document (PDF)
          bronze_photo_ids.py                  # ai_parse_document (JPEG)
          silver_applications.py               # 3-way join on application_id
          gold_features.py                     # ML features + verification signals
```

## Configuration

| Variable | Description | Default |
|---|---|---|
| `catalog` | Unity Catalog catalog | `mfg_mc_se_sa` |
| `schema` | Schema for tables and volume | `cdk` |
| `warehouse_id` | SQL warehouse for jobs | `bce0a02b2be86f1b` |
