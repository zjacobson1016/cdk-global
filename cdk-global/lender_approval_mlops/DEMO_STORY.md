# CDK Global: Building an Agentic Lending Platform on Databricks

> **Demo narrative for CDK Global** — Walking through how to build an end-to-end
> agentic architecture on Databricks, from raw data ingestion through AI-powered
> document processing, ML decisioning, and conversational agents.

---

## The Business Problem

CDK Global processes millions of auto loan applications annually across its dealer network. Today that process looks like this:

| Pain Point | Current State | Cost |
|---|---|---|
| **Manual document review** | Underwriters read pay stubs and check IDs by hand | 15-25 min per application |
| **Income fraud exposure** | Self-reported income taken at face value | 2-5% of funded loans have income discrepancies |
| **Fragmented systems** | Application data, documents, and decisions live in separate tools | No unified audit trail |
| **Stale models** | Retraining happens quarterly at best | Model accuracy degrades as market shifts |
| **No self-service analytics** | F&I managers can't answer their own data questions | Every question requires a data team ticket |

**What if a dealer's F&I manager could ask a single system**: *"Ask questions about customer lender profile natural language,Gain insights into customer profile metric compared to lender standards, Score this application, find me the best lender rate, and show me our approval trends this month"* — and get an answer in seconds?

That's what we're building.

---

## Architecture Overview

```
                         ┌─────────────────────────────────────────────────┐
                         │        CDK Lending Supervisor (MAS) in Web App             │
                         │   "Route my question to the right agent"        │
                         └──────┬──────────────┬──────────────┬────────────┘
                                │              │              │
                    ┌───────────▼──┐   ┌───────▼──────┐  ┌───▼──────────────┐
                    │  Lending     │   │  Loan        │  │  Lender          │
                    │  Analytics   │   │  Approval    │  │  Shopping        │
                    │  (Genie)     │   │  (ML Model)  │  │  (shop_lenders)  │
                    └───────┬──────┘   └───────┬──────┘  └───┬──────────────┘
                            │                  │             │
          ┌─────────────────▼──────────────────▼─────────────▼─────────────┐
          │                    Unity Catalog (Governed)                     │
          │  Tables │ Models │ Functions │ Features │ Volumes │ Metrics    │
          └─────────────────────────────┬──────────────────────────────────┘
                                        │
          ┌────────────────┬────────────┼────────────┬─────────────────────┐
          │                │            │            │                     │
    ┌─────▼──────┐  ┌──────▼─────┐  ┌──▼───────┐  ┌▼──────────┐  ┌──────▼──────┐
    │ Structured │  │ Pay Stubs  │  │ Photo IDs│  │ Lender    │  │ Metric     │
    │ Apps       │  │ (PDF)      │  │ (JPEG)   │  │ Programs  │  │ View       │
    │ (Parquet)  │  │ ai_parse   │  │ ai_parse │  │ Reference │  │ (governed  │
    │            │  │ + ai_query │  │ + ai_query│  │ Data      │  │  KPIs)     │
    └─────┬──────┘  └──────┬─────┘  └──┬───────┘  └┬──────────┘  └────────────┘
          │                │            │           │
    ══════╪════════════════╪════════════╪═══════════╪══ SDP Pipeline ═══════════
          ▼                ▼            ▼           │
     bronze_apps    bronze_pay_stubs  bronze_ids    │
          │                │            │           │
          └────────┬───────┘────────────┘           │
                   ▼                                │
          silver_applications (3-way JOIN)          │
                   │                                │
                   ▼                                │
          gold_lender_features ◄────────────────────┘
                   │
    ═══════════════╪════════════════════════════ ML Pipeline ═══════════════
                   ▼
          Feature Engineering (Feature Store + UC Functions)
                   │
                   ▼
          Model Training (Optuna HPO + Business Rules)
                   │
                   ▼
          Champion / Challenger (Automated Promotion)
                   │
              ┌────┴─────┐
              ▼          ▼
        Batch Inf.   Real-Time Serving
              │          (sub-second decisions)
              ▼
        Monitoring → Drift Detection → Auto-Retrain Loop
```

---

## Demo Walkthrough

### Act 1: Start with the Outcome — The Agentic Experience

> **Key message**: *Start with what the business user sees, then peel back the layers.*

#### Scene 1: The Multi-Agent Supervisor

Open the **CDK Lending Supervisor** — a Multi-Agent Supervisor (MAS) that orchestrates three specialized agents behind a single conversational interface.

Set the scene: *You're Sarah, an F&I manager at a high-volume dealership in Dallas. It's Saturday morning — the busiest day of the week. A customer is sitting across the desk with a trade-in and a specific vehicle in mind. Sarah needs to move fast without cutting corners.*

---

**Turn 1** — Sarah checks the landscape *(routes to Lending Analytics / Genie)*:

> *"What are the approval rates by credit tier for the most recent month available?" I want to know where we stand before I start working this deal."*
> *Can you provide the total credit_score for application_id APP-000010 from the feature store*

The supervisor recognizes this as a data question and routes it to the **Lending Analytics** agent (a Genie Space). Genie translates the question to SQL, queries `gold_lender_features`, and returns:

| Credit Tier | Approval Rate |
|---|---|
| Super Prime (740+) | 95.6% |
| Prime (700-739) | 91.9% |
| Near Prime (660-699) | 89.3% |
| Subprime (600-659) | 85.3% |
| Deep Subprime (<600) | 77.2% |

Sarah sees that near-prime borrowers are getting approved almost 90% of the time. Good — her customer pulled a 710, so she's feeling confident.

---

**Turn 2** — Sarah runs the application through the model *(routes to Loan Approval / ML Model)*:

> *"Great. I just submitted this customer's application — it's APP-000010. Can you score it?"*

The conversation continues naturally. The supervisor recognizes the application ID and routes to the **Loan Approval** agent, which calls the `predict_loan_approval` UC function — a wrapper around the real-time model serving endpoint:

```json
{
  "prediction": 1,
  "ml_prediction": 1,
  "ml_probability": 0.8362,
  "income_check": "PASS",
  "id_check": "PASS",
  "decision_reason": "APPROVED by ML model (all checks passed)"
}
```

Sarah sees the approval instantly: 83.6% confidence, income verified against the pay stub, photo ID is valid and not expired. She doesn't need to wait for an underwriter.

---

**Turn 3** — Sarah shops for the best rate *(routes to Lender Shopping / shop_lenders)*:

> *"Perfect — approved. Now find me the best rates for this applicant?"*
> *"Assume values of loan term: 60 months and model year: 2025"*

Without leaving the conversation, the supervisor routes to the **Lender Shopping** agent, which calls the `shop_lenders` UC function across 20 programs from 8 lenders:

| Lender | Program | APR | Monthly Payment | Approval Likelihood |
|---|---|---|---|---|
| Chase Auto | Preferred New | 3.49% | $636.55 | LOW |
| Navy Federal | New Auto Loan | 3.79% | $641.27 | MEDIUM |
| Ally Financial | SmartAuto New | 3.99% | $644.42 | MEDIUM |
| Wells Fargo | Prime Auto | 4.29% | $649.17 | MEDIUM |
| Capital One | Prime New Vehicle | 4.49% | $652.35 | MEDIUM |
| ... | ... | ... | ... | ... |

Sarah sees that Ally at 3.99% with MEDIUM approval likelihood is probably the sweet spot — Navy Federal's 3.79% is better on rate but Chase's 3.49% shows LOW likelihood for this profile. She picks Ally, walks back to the customer, and closes the deal.

---

**The story in 90 seconds**: Sarah checked the market, scored the application, and found the best rate — all in one conversation, in under two minutes. Three different systems (analytics warehouse, ML model, lender database) answered her questions without her ever knowing they were separate.

**Talking point**: *This is what agentic AI looks like in practice. It's not a chatbot — it's an orchestration layer that routes each question to the right specialist. The supervisor handles the routing; the agents handle the expertise. The F&I manager just has a conversation.*

---

#### Scene 2: The Genie Space — Self-Service Analytics

Zoom into the **CDK Lending Analytics** Genie Space. This connects directly to four Unity Catalog tables:

| Table | Rows | Purpose |
|---|---|---|
| `gold_lender_features` | 15,000 | ML-ready application features |
| `lender_programs` | 18 | Lender program reference data |
| `lender_approval_inference_table` | 1,000 | Model predictions with reasoning |
| `lender_approval_offline_inference` | 1,000 | Batch inference results |

Ask natural language questions that span both structured and unstructured data:

- *"What percentage of applications have full document verification?"*
- *"Which lenders offer programs for credit scores below 600?"*
- *"Show me monthly application volume trends by loan purpose"*
- *"What is the model prediction breakdown from the latest batch inference?"*

**Talking point**: *No SQL required. F&I managers, regional directors, and compliance teams can explore the data themselves — no ticket to the data team needed.*

---

#### Scene 3: The Metric View — Governed Business KPIs

Behind the Genie Space sits a **Metric View** (`lending_analytics_metrics`) that defines standardized, governed business metrics. This ensures everyone in the organization measures things the same way.

```sql
SELECT `Credit Tier`, `Loan Purpose`,
       MEASURE(`Total Applications`),
       MEASURE(`Approval Rate`),
       MEASURE(`Avg Loan Amount`),
       MEASURE(`Avg Credit Score`)
FROM mfg_mc_se_sa.cdk.lending_analytics_metrics
GROUP BY `Credit Tier`, `Loan Purpose`
```

**12 Dimensions** including Credit Tier, Loan Purpose, DTI Bucket, Doc Completeness Level, Employment Tenure, Applicant State

**17 Measures** including Total Applications, Approval Rate, Total Loan Volume, Median Credit Score, Pay Stub Submission Rate, Full Doc Rate

**Talking point**: *The metric view is the single source of truth. Whether a metric appears in Genie, a dashboard, or an API call — it's defined once, governed by Unity Catalog, and consistent everywhere.*

---

### Act 2: Peel Back the Layers — How the Data Gets There

> **Key message**: *Now let's look at how we build the foundation these agents sit on.*

#### Scene 4: Three Data Sources, One Pipeline

The lending platform ingests three types of data — all tied together by `application_id`:

| Source | Format | How It Arrives | What We Extract |
|---|---|---|---|
| **Loan Applications** | Parquet | Structured data from the DMS | Income, credit score, DTI, loan amount, purpose |
| **Pay Stubs** | PDF | Uploaded by applicant | Employer, gross/net pay, YTD totals |
| **Photo IDs** | JPEG | Scanned at the dealership | Full name, DOB, license number, expiration date |

**Show the UC Volume** — all three data types land in Unity Catalog Volumes:
```
/Volumes/mfg_mc_se_sa/cdk/raw_data/
  ├── applications/    (parquet files)
  ├── pay_stubs/       (PDF files — APP-000001_paystub.pdf)
  └── photo_ids/       (JPEG files — APP-000001_photoid.jpg)
```

**Talking point**: *Structured and unstructured data side by side in the same governed namespace. No separate document management system needed.*

---

#### Scene 5: AI-Powered Document Processing

This is where Databricks AI Functions eliminate manual document review.

**Pay stub processing** (`bronze_pay_stubs`):

```python
# Step 1: Parse PDF into text
.withColumn("parsed", F.expr("ai_parse_document(content)"))

# Step 2: Extract structured fields using LLM
.withColumn("extracted_json",
    F.expr("ai_query('databricks-meta-llama-3-3-70b-instruct',
            concat(extraction_prompt, full_text))")
)
```

From a PDF pay stub, the pipeline extracts: `employee_name`, `employer_name`, `gross_pay`, `net_pay`, `ytd_gross`, `ytd_net`, `pay_date` — all typed and ready for joins.

**Photo ID processing** (`bronze_photo_ids`):

Same pattern — `ai_parse_document` reads the JPEG, `ai_query` extracts: `full_name`, `date_of_birth`, `license_number`, `state`, `expiration_date`.

**Talking point**: *Two SQL functions — `ai_parse_document` and `ai_query` — replace an entire document processing pipeline. No external OCR service, no separate ML model to maintain. It's just SQL in the same pipeline as your structured data.*

---

#### Scene 6: The Medallion Pipeline (SDP)

Show the **Spark Declarative Pipeline** that ties everything together:

```
bronze_applications  ──┐
bronze_pay_stubs    ───┤──► silver_applications ──► gold_lender_features
bronze_photo_ids    ───┘     (3-way LEFT JOIN        (feature engineering:
                              on application_id)      income verification,
                                                      identity checks,
                                                      doc completeness)
```

**Silver layer** — Three-way LEFT JOIN on `application_id`. Applications are retained even when supporting documents are missing (this is realistic — not every applicant uploads every document).

**Gold layer** — Derived ML features:
- `verified_annual_income` — pay stub biweekly × 26
- `income_verification_ratio` — verified vs. self-reported income
- `name_match` — does the pay stub name match the photo ID name?
- `id_expired` — is the photo ID still valid?
- `doc_completeness` — 0 (none), 1 (partial), 2 (full)

**Talking point**: *This is declarative — you define WHAT you want, not HOW to compute it. The pipeline handles incremental processing, schema evolution, and retry logic automatically. And the AI functions run inside the pipeline, not as a separate step.*

---

### Act 3: The ML System — From Features to Decisions

> **Key message**: *The model is just one piece. The real value is the system around it.*

#### How the ML Tables Fit Together

Seven tables form the backbone of the ML system. Each serves a distinct purpose, and they connect through `application_id` and `transaction_ts`:

```
                        gold_lender_features
                        (SDP pipeline output)
                                │
                    ┌───────────┼───────────┐
                    ▼                       ▼
          feature_table              label_table
          ─────────────              ───────────
          All gold columns           application_id
          registered in              approved (target)
          Feature Store              split (train/test)
          PK: application_id         ─────────┬─────
              transaction_ts                  │
            ┌───────┤                         │
            │       │                         │
            ▼       │                         │
    online_feature  │                         │
    _table          │                         │
    ────────────    │                         │
    Synced copy     │       ┌─────────────────┘
    for real-time   │       │
    serving         │       ▼
    (Online Store)  │   app_ids_table
                    │   ─────────────
                    │   application_id    ◄── Filtered to split='test'
                    │   transaction_ts        from label_table
                    │   split
                    │       │
                    │       │  fe.score_batch
                    │       │  (point-in-time join
                    │       │   against feature_table)
                    │       ▼
                    │   offline_inference_table
                    │   ───────────────────────
                    │   application_id, prediction
                    │   income_check, id_check
                    │   decision_reason, model_version
                    │       │
                    │       │  LEFT JOIN on application_id
                    │       │  + label_table.approved
                    │       ▼
                    │   inference_table  ◄──── Lakehouse Monitoring
                    │   ───────────────        attaches here
                    │   predictions + labels
                    │   (unified view)
                    │       │
                    │       │  Filtered to split='test'
                    │       │  + sampled (LIMIT 1000)
                    │       ▼
                    └─► baseline_table
                        ──────────────
                        Reference distribution
                        for drift detection
```

| Table | Created By | Purpose | Key Relationship |
|---|---|---|---|
| **feature_table** | `01_feature_engineering` | Feature Store — all ML features with point-in-time keys | Source: `gold_lender_features` |
| **label_table** | `01_feature_engineering` | Ground truth labels + train/test split | Joined to features by `application_id` + `transaction_ts` |
| **app_ids_table** | `01_feature_engineering` | Test-split IDs for batch scoring | Subset of `label_table` where `split='test'` |
| **online_feature_table** | `06_serve_features` | Online Store sync of feature_table | Published from `feature_table` for real-time lookup |
| **offline_inference_table** | `05_batch_inference` | Batch predictions with reasoning | `app_ids_table` scored via `fe.score_batch` against `feature_table` |
| **inference_table** | `07_model_monitoring` | Predictions + labels for monitoring | `offline_inference_table` LEFT JOIN `label_table` |
| **baseline_table** | `07_model_monitoring` | Reference distribution for drift | Subset of `inference_table` (test split, 1000 rows) |

#### Scene 7: Feature Engineering with Feature Store

Notebook `01_feature_engineering` creates:

1. **Feature Table** — All gold columns registered in the Feature Store for point-in-time lookup
2. **Label Table** — `application_id`, `approved`, `split` (train/test)
3. **Three UC Functions** used as on-demand Feature Functions:
   - `affordability_ratio(income, loan_amount)` — loan-to-income ratio
   - `income_validation(income, verified_income)` — 1=pass, 0=fail, -1=missing
   - `id_expiration_check(expiration_date)` — 1=valid, 0=expired, -1=missing

**Talking point**: *These functions are computed on-demand at training AND serving time. Define the business rule once as a UC function, and it's automatically applied everywhere — batch, real-time, monitoring.*

---

#### Scene 8: Training with Optuna HPO + Business Rules

The model training (`02_model_training_hpo_optuna`) does three things:

1. **Optuna HPO** — Searches across LogisticRegression, RandomForest, and LightGBM with parallel trials
2. **Custom PyFunc wrapper** (`LenderApprovalWithRules`) — Applies deterministic business rules on top of the ML prediction:

| Rule | Logic | Override |
|---|---|---|
| **Income validation** | Pay stub income must be 70-150% of self-reported | FAIL → auto-deny |
| **ID expiration** | Photo ID must not be expired | FAIL → auto-deny |

3. **Structured output** — Every prediction returns a full decision record:

```json
{
  "prediction": 0,
  "ml_prediction": 1,
  "ml_probability": 0.87,
  "income_check": "FAIL",
  "id_check": "PASS",
  "decision_reason": "DENIED by rules: Income mismatch (pay stub vs application)"
}
```

**Talking point**: *The ML model said "approve" but the business rule caught an income discrepancy and overrode the decision. This is how you build trust — the model accelerates good decisions, and the rules catch what the model can't see. And every decision is explainable.*

---

#### Scene 9: Champion / Challenger Deployment

The MLOps lifecycle is fully automated:

```
Train (Optuna HPO)
  └─► Register Challenger in Unity Catalog
        └─► Validate (schema, predictions, metric comparison vs. Champion)
              └─► Promote to Champion (if validation passes)
                    └─► Deploy to Model Serving endpoint
```

- `03b` registers the best model as **Challenger**
- `04a` validates: does it have the right schema? Does it predict sensible values? Is its F1 score better than Champion?
- `04b` promotes to **Champion** if the `validation_status` tag is `approved`

**Talking point**: *No model goes to production without validation. And when it does, the Champion alias rotates automatically — no manual deployment, no downtime.*

---

#### Scene 10: Real-Time Serving with Feature Lookup

The serving endpoint (`lender_approval_serving_cdk`) takes a single `application_id` and:

1. Looks up all features from the **online feature store** (synced from the Feature Table)
2. Evaluates the three **Feature Functions** on-demand (affordability, income validation, ID check)
3. Runs the ML model
4. Applies the deterministic business rules
5. Returns the structured decision with reasoning

```
Request:  { "application_id": "APP-003249" }

Response: { "prediction": 1, "ml_probability": 0.76,
            "income_check": "MISSING", "id_check": "MISSING",
            "decision_reason": "APPROVED by ML model (pending doc verification)" }
```

**And now it's also a UC function**:
```sql
SELECT mfg_mc_se_sa.cdk.predict_loan_approval('APP-003249')
```

The `predict_loan_approval` UC function wraps the endpoint using `ai_query()`, making it callable from SQL, agents, dashboards, or any tool in the Databricks ecosystem.

**Talking point**: *Sub-second decisions at the point of sale. The dealer submits an application ID and gets an instant decision with full reasoning — approved or denied, and exactly why.*

---

#### Scene 11: Monitoring, Drift, and Auto-Retrain

The system monitors itself:

1. **Lakehouse Monitoring** (`07_model_monitoring`) — Attaches to the unified inference table, tracking prediction distributions, feature drift, and label drift
2. **Drift Detection** (`08_drift_detection`) — Counts KS test and Chi-squared violations across all features
3. **Conditional Retrain** — If `all_violations_count > 0`, the retraining job triggers automatically

```
Monitor inference table
  └─► Compute drift metrics (KS, Chi-squared, PSI)
        └─► Count violations
              └─► violations > 0?
                    ├─ YES → Retrain → Register Challenger → Validate → Promote
                    └─ NO  → Continue monitoring
```

**Talking point**: *The model doesn't wait for quarterly retraining. When market conditions shift — interest rate changes, vehicle price fluctuations — the system detects the drift and retrains automatically. The Champion/Challenger pattern ensures the new model is validated before it goes live.*

---

### Act 4: The Agentic Layer — Tying It All Together

> **Key message**: *Agents are the interface layer. They don't replace the data platform — they sit on top of it.*

#### Scene 12: Three UC Functions as Agent Tools

Everything the agents do is powered by governed UC functions:

| UC Function | Purpose | Used By |
|---|---|---|
| `predict_loan_approval(app_id)` | Real-time ML scoring via model endpoint | Loan Approval Agent |
| `shop_lenders(credit, income, amount, term, year)` | Multi-lender rate comparison | Lender Shopping Agent |
| `affordability_ratio(income, loan_amount)` | Loan-to-income ratio | Feature Store + Agents |
| `income_validation(income, verified_income)` | Pay stub vs. application check | Model rules + Agents |
| `id_expiration_check(expiration_date)` | Photo ID validity | Model rules + Agents |

**Talking point**: *Every agent tool is a UC function — governed, versioned, auditable. The same function that runs in the ML pipeline at training time is the same function the agent calls at inference time. No duplication, no drift between training and serving logic.*

---

#### Scene 13: Lender Programs — The Rate Shopping Engine

The `lender_programs` table contains 20 programs from 8 lenders:

| Lender | Programs | Min Credit | APR Range |
|---|---|---|---|
| Capital One Auto Finance | Prime New, Prime Used, Near Prime | 600-700 | 4.49%-14.99% |
| Ally Financial | SmartAuto New, SmartAuto Used, Subprime Recovery | 520-680 | 3.99%-21.99% |
| Chase Auto | Preferred New, Standard Used | 660-720 | 3.49%-9.49% |
| TD Auto Finance | Tier 1 New, Tier 2 CPO | 680-740 | 2.99%-7.49% |
| Wells Fargo | Prime Auto, Non-Prime | 580-700 | 4.29%-17.99% |
| Westlake Financial | Deep Subprime, Second Chance | 450-500 | 14.49%-24.99% |
| Navy Federal CU | New Auto, Used Auto | 640-670 | 3.79%-8.99% |
| AmeriCredit (GM Financial) | GM Loyalty New, Standard Used | 550-620 | 4.99%-17.49% |

The `shop_lenders` function matches a borrower profile against all active programs, computes estimated monthly payments, and ranks by approval likelihood.

**Talking point**: *This is the kind of data that lives in spreadsheets today. By putting it in Unity Catalog with a governed function on top, every dealer gets the same rates, the same logic, the same audit trail.*

---

### Act 5: Deployed as Code — Databricks Asset Bundles

> **Key message**: *Everything you've seen is infrastructure-as-code.*

The entire platform is defined in a **Databricks Asset Bundle**:

```
lender_approval_mlops/
  databricks.yml                         # Bundle config + variables
  resources/
    lender_approval_mlops_pipeline.yml   # SDP pipeline definition
    lender_approval_mlops_job.yml        # Job DAG (13 tasks)
  src/
    notebooks/
      00-08: Data gen → Pipeline → Training → Serving → Monitoring
      09a:   Lender programs + shop_lenders UC function
      09b:   Metric view creation
      09c:   Genie Space + UC function wrappers + MAS scaffold
    pipelines/lender_approval_etl/
      transformations/
        bronze → silver → gold (5 files)
```

```bash
# Deploy everything with two commands
databricks bundle validate -t dev
databricks bundle deploy -t dev
```

**Talking point**: *This isn't a demo in a notebook. It's a production-grade system that can be deployed to any workspace, any environment, with a single CLI command. The same bundle deploys to dev, staging, and prod with variable overrides.*

---

## The Complete Value Chain

```
RAW DATA           AI PROCESSING          ML SYSTEM              AGENTIC LAYER
─────────          ─────────────          ─────────              ─────────────
Applications ───►  Auto Loader     ───►   Feature Store    ───►  Genie Space
Pay Stubs    ───►  ai_parse_document ─►   Optuna HPO       ───►  predict_loan_approval()
Photo IDs    ───►  ai_query         ───►  Business Rules   ───►  shop_lenders()
Lender Data  ───►  Medallion Pipeline ──► Champion/Chall.  ───►  MAS Supervisor
                                          Real-Time Serving      Metric View
                                          Monitoring + Drift
```

| Layer | Databricks Capability | Business Outcome |
|---|---|---|
| **Ingestion** | UC Volumes + Auto Loader + SDP | All data types in one governed platform |
| **AI Processing** | `ai_parse_document` + `ai_query` | Eliminate manual document review |
| **ML Pipeline** | Feature Store + Optuna + MLflow | Automated, reproducible model lifecycle |
| **Business Rules** | UC Functions + PyFunc wrapper | Deterministic overrides with full reasoning |
| **Serving** | Model Serving + Online Store | Sub-second decisions at point of sale |
| **Monitoring** | Lakehouse Monitoring + Drift | Auto-retrain when market conditions shift |
| **Analytics** | Metric Views + Genie Space | Self-service insights for business users |
| **Agents** | UC Functions + MAS | Conversational interface unifying all capabilities |
| **Deployment** | Asset Bundles | Infrastructure-as-code, multi-environment |

---

## Demo Run Order

For a live demo, step through in this order:

| Step | What to Show | Time |
|---|---|---|
| 1 | **Genie Space** — ask 2-3 analytics questions | 3 min |
| 2 | **predict_loan_approval** — score an application via UC function | 1 min |
| 3 | **shop_lenders** — find rates for a borrower profile | 1 min |
| 4 | **Metric View** — show governed KPIs with MEASURE() syntax | 2 min |
| 5 | **UC Volumes** — show raw PDFs + JPEGs alongside parquet | 1 min |
| 6 | **SDP Pipeline** — walk through bronze → silver → gold | 3 min |
| 7 | **ai_parse_document + ai_query** — show document extraction SQL | 2 min |
| 8 | **Model Training** — Optuna HPO + business rules wrapper | 3 min |
| 9 | **Model Serving endpoint** — real-time response with reasoning | 2 min |
| 10 | **Monitoring + Drift** — show inference table + violation counts | 2 min |
| 11 | **Asset Bundle** — show `databricks.yml` + deploy command | 1 min |
| **Total** | | **~21 min** |

---

## Key Talking Points by Persona

### For the CTO / VP Engineering
- **Platform consolidation**: One platform replaces separate systems for data, ML, document processing, and analytics
- **Infrastructure-as-code**: Asset Bundles enable GitOps for the entire ML lifecycle
- **Governance**: Unity Catalog provides a single control plane for data, models, functions, and agents

### For the Data Science / ML Team
- **Feature Store**: Point-in-time lookups with online/offline consistency
- **UC Functions as Feature Functions**: Business rules computed on-demand at train and serve time
- **Optuna + MLflow**: Distributed HPO with automatic experiment tracking
- **Champion/Challenger**: Automated model promotion with validation gates

### For the Business / F&I Leadership
- **Self-service analytics**: Genie Space lets anyone ask questions without SQL
- **Explainable decisions**: Every approval/denial includes a `decision_reason`
- **Rate shopping**: Dealers can instantly compare 20 programs from 8 lenders
- **Compliance**: Full audit trail from raw document to final decision

### For the Compliance / Risk Team
- **Deterministic rules**: Income validation and ID expiration checks can't be overridden by the model
- **Structured output**: Every prediction is logged with reasoning
- **Drift detection**: Model accuracy is continuously monitored
- **Lineage**: Unity Catalog traces every table, model, and function back to its source
