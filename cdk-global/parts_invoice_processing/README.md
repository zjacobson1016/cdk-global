# Parts Invoice Processing — CDK Global

Automated parts invoice processing pipeline for automotive dealerships, built end-to-end on Databricks. Raw invoice data and PDFs flow through a medallion architecture, are enriched with AI-powered document parsing and entity extraction, matched against purchase orders and receiving reports, and surfaced through an agentic approval workflow with Slack notifications.

The system culminates in a **Multi-Agent Supervisor** that orchestrates a dedicated **Invoice Processing Agent** (for invoice lookup, approval actions, and supplier analytics) alongside a **Genie Space** (for ad-hoc SQL exploration of the approval pipeline).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                        DATA SOURCES                                         │
│                                                                                             │
│   ┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────────────┐   │
│   │  Synthetic Generator │    │   PDF Invoice Gen    │    │     Lakebase Provisioned     │   │
│   │  (Faker + Spark)     │    │   (FPDF2)            │    │     (PostgreSQL)             │   │
│   │                      │    │                      │    │                              │   │
│   │  • Suppliers (15)    │    │  • Invoice PDFs (50) │    │  • invoice_approval_log      │   │
│   │  • POs (300)         │    │    rendered from      │    │    (approval state machine)  │   │
│   │  • Receiving (270)   │    │    structured data    │    │                              │   │
│   │  • Invoices (200)    │    │                      │    │                              │   │
│   │  • Emails (250)      │    │                      │    │                              │   │
│   └────────┬─────────────┘    └────────┬─────────────┘    └──────────────┬───────────────┘   │
│            │ Parquet                    │ PDF                             │                   │
│            ▼                           ▼                                 │                   │
│   ┌────────────────────────────────────────────┐                         │                   │
│   │       Unity Catalog Volume: raw_data       │                         │                   │
│   │  /suppliers/  /purchase_orders/  /invoices/ │                         │                   │
│   │  /receiving/  /emails/  /invoice_pdfs/      │                         │                   │
│   └────────────────────┬───────────────────────┘                         │                   │
└────────────────────────┼─────────────────────────────────────────────────┼───────────────────┘
                         │                                                 │
┌────────────────────────┼─────────────────────────────────────────────────┼───────────────────┐
│                        ▼         SPARK DECLARATIVE PIPELINE (SDP)        │                   │
│                                                                          │                   │
│   ┌─────────────────────────────────────────────────────────────┐         │                   │
│   │  BRONZE  ── Streaming Tables via read_files()               │         │                   │
│   │                                                             │         │                   │
│   │  bronze_suppliers ─ bronze_purchase_orders ─ bronze_invoices │         │                   │
│   │  bronze_receiving_reports ─ bronze_emails                    │         │                   │
│   │  bronze_invoice_documents (binaryFile)                      │         │                   │
│   └──────────────────────┬──────────────────────────────────────┘         │                   │
│                          │                                               │                   │
│   ┌──────────────────────▼──────────────────────────────────────┐         │                   │
│   │  SILVER  ── Cleaned + AI-Enriched                           │         │                   │
│   │                                                             │         │                   │
│   │  silver_suppliers ─ silver_purchase_orders ─ silver_invoices │         │                   │
│   │  silver_receiving_reports ─ silver_emails                    │         │                   │
│   │                                                             │         │                   │
│   │  ┌───────────────────────────────────────────────────────┐  │         │                   │
│   │  │  ai_parse_document(content)                           │  │         │                   │
│   │  │  ──► silver_parsed_invoice_documents                  │  │         │                   │
│   │  │                                                       │  │         │                   │
│   │  │  ai_query('databricks-meta-llama-3-3-70b-instruct')  │  │         │                   │
│   │  │  ──► silver_parsed_invoices_flat (structured JSON)    │  │         │                   │
│   │  └───────────────────────────────────────────────────────┘  │         │                   │
│   └──────────────────────┬──────────────────────────────────────┘         │                   │
│                          │                                               │                   │
│   ┌──────────────────────▼──────────────────────────────────────┐         │                   │
│   │  GOLD  ── Materialized View                                 │         │                   │
│   │                                                             │         │                   │
│   │  gold_invoice_match                                         │         │                   │
│   │  ├── 3-Way Match: Invoice PDF ↔ PO ↔ Receiving Report      │         │                   │
│   │  ├── match_status: MATCHED | PRICE_DISCREPANCY | ...        │         │                   │
│   │  ├── price_variance_pct, quantity_variance                  │         │                   │
│   │  ├── invoice_classification: STANDARD | DISCREPANCY | ...   │         │                   │
│   │  └── approval_route: AUTO_APPROVED | SERVICE_MANAGER        │         │                   │
│   │         | PARTS_DIRECTOR | GENERAL_MANAGER                  │         │                   │
│   │         | EXCEPTION_REVIEW | RECEIVING_REVIEW | PO_REQUIRED │         │                   │
│   └─────────────────────────────────────────────────────────────┘         │                   │
│                                                                          │                   │
└──────────────────────────────────────────────────────────────────────────┼───────────────────┘
                         │                                                 │
                         │  ┌──────────────────────────────────────────────┘
                         │  │
┌────────────────────────┼──┼─────────────────────────────────────────────────────────────────┐
│                        ▼  ▼       AGENTIC LAYER                                             │
│                                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐    │
│   │  Unity Catalog Functions (9)                                                        │    │
│   │                                                                                     │    │
│   │  READ (from gold_invoice_match):          READ (from Lakebase federation):           │    │
│   │  ├─ get_invoice_details()                 ├─ get_approval_status()                   │    │
│   │  ├─ search_invoices_by_supplier()         ├─ get_pending_approvals_for_route()       │    │
│   │  ├─ get_invoices_by_route()               └─ get_approval_summary()                  │    │
│   │  ├─ get_supplier_performance()                                                      │    │
│   │  └─ get_invoice_summary()                 AGENT QUERY:                               │    │
│   │                                           └─ ask_parts_invoice_agent()               │    │
│   └──────────────────────────────┬──────────────────────────────────────────────────────┘    │
│                                  │                                                          │
│   ┌──────────────────────────────▼──────────────────────────────────────────────────────┐    │
│   │  Invoice Processing Agent  (LangGraph + ResponsesAgent)                             │    │
│   │                                                                                     │    │
│   │  Intent Router ──► process_invoice ──► Lookup → Classify → Match → Submit           │    │
│   │                 ──► approve_invoice ──► Update Lakebase + Slack ✓                    │    │
│   │                 ──► reject_invoice  ──► Update Lakebase + Slack ✗                    │    │
│   │                 ──► escalate_invoice──► Reroute + Slack ↑                            │    │
│   │                 ──► check_status    ──► Query approval_log                           │    │
│   │                 ──► my_approvals    ──► Pending items by route                       │    │
│   │                 ──► general_query   ──► Free-form invoice Q&A                        │    │
│   │                                                                                     │    │
│   │  Tools:  8 UC Functions (read)  +  4 Approval Tools (write via Lakebase/psycopg)    │    │
│   │  LLM:   databricks-meta-llama-3-3-70b-instruct                                     │    │
│   └──────────────────────────────┬──────────────────────────────────────────────────────┘    │
│                                  │                                                          │
│   ┌──────────────────────────────▼──────────────────────┐  ┌────────────────────────────┐   │
│   │  Model Serving Endpoint                              │  │  Slack Notifications       │   │
│   │  agents_mfg_mc_se_sa-cdk-parts_invoice_agent         │  │                            │   │
│   │                                                      │  │  #service-approvals        │   │
│   │  Registered: mfg_mc_se_sa.cdk.parts_invoice_agent    │  │  #parts-approvals          │   │
│   └──────────────────────┬───────────────────────────────┘  │  #gm-approvals             │   │
│                          │                                  │  #invoice-exceptions        │   │
│                          │                                  │  #invoice-auto-approved     │   │
│                          │                                  └────────────────────────────┘   │
└──────────────────────────┼──────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────────────────────────────────┐
│                          ▼       MULTI-AGENT SUPERVISOR                                     │
│                                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐    │
│   │                    Databricks Multi-Agent Supervisor                                 │    │
│   │                                                                                     │    │
│   │   ┌───────────────────────────────┐     ┌────────────────────────────────────────┐  │    │
│   │   │  Invoice Processing Agent     │     │  Genie Space                           │  │    │
│   │   │                               │     │  Invoice Approval Analytics            │  │    │
│   │   │  "Process INV-0042"           │     │                                        │  │    │
│   │   │  "Approve INV-0042"           │     │  "How many invoices are pending        │  │    │
│   │   │  "What's the match status     │     │   for the parts director?"             │  │    │
│   │   │   for Acme Parts?"            │     │  "Show me top vendors by               │  │    │
│   │   │  "Show my pending approvals"  │     │   invoice discrepancy rate"            │  │    │
│   │   │                               │     │  "Total value of auto-approved         │  │    │
│   │   │                               │     │   invoices this month"                 │  │    │
│   │   └───────────────────────────────┘     └────────────────────────────────────────┘  │    │
│   │                                                                                     │    │
│   └─────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────────────────────┐    │
│   │  AI/BI Dashboard  (invoice_metrics metric view)                                     │    │
│   │  Dimensions: match status, approval route, vendor, department, month                │    │
│   │  Measures: invoice count, total value, match rate, auto-approved %, avg variance    │    │
│   └─────────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
parts_invoice_processing/
├── databricks.yml                              # DAB config (targets: dev, prod)
├── resources/
│   ├── parts_invoice_processing_pipeline.yml   # Serverless SDP pipeline
│   └── parts_invoice_processing_job.yml        # End-to-end orchestration job
├── scripts/
│   ├── 01_generate_synthetic_data.py           # Faker → Parquet (suppliers, POs, invoices, …)
│   ├── 02_generate_invoice_pdfs.py             # FPDF2 → PDF invoices in UC volume
│   └── 03_create_approval_tables.py            # Lakebase PostgreSQL setup
├── src/
│   ├── pipelines/
│   │   ├── 01_bronze.sql                       # Streaming ingestion via read_files()
│   │   ├── 02_silver.sql                       # Validation + ai_parse_document + ai_query
│   │   └── 03_gold.sql                         # 3-way match, classification, approval routing
│   ├── agent/
│   │   ├── agent.py                            # LangGraph ResponsesAgent
│   │   ├── approval_tools.py                   # Lakebase write tools (approve/reject/escalate)
│   │   ├── slack_notifier.py                   # Slack Block Kit notifications by route
│   │   ├── log_model.py                        # MLflow model registration
│   │   ├── deploy_agent.py                     # Deploy to model serving
│   │   ├── test_agent.py                       # Agent test notebook
│   │   └── AGENT_WALKTHROUGH.md                # Design walkthrough
│   ├── uc_functions/
│   │   └── create_functions.py                 # 9 UC SQL functions (read + agent query)
│   └── metric_views/
│       └── create_invoice_metrics.py           # AI/BI metric view definition
└── README.md
```

---

## Components

### 1. Data Generation

| Script | Purpose | Output |
|--------|---------|--------|
| `01_generate_synthetic_data.py` | Generate realistic dealership data with Faker | Parquet files in `raw_data` volume |
| `02_generate_invoice_pdfs.py` | Render structured invoice data into PDFs | PDF files in `raw_data/invoice_pdfs/` |
| `03_create_approval_tables.py` | Provision Lakebase instance and approval table | `invoice_approval_log` in PostgreSQL |

Synthetic data includes 15 suppliers, 300 purchase orders, 270 receiving reports, 200 invoices (with ~28% intentional discrepancies), and 250 email records.

### 2. Medallion Pipeline (Spark Declarative Pipeline)

**Bronze** — Raw ingestion via `STREAM read_files()` from UC volumes. Six streaming tables including binary PDF ingestion.

**Silver** — Data cleaning, type casting, and AI enrichment:
- `ai_parse_document()` extracts text from invoice PDFs
- `ai_query()` with Llama 3.3 70B performs structured entity extraction (vendor, PO number, line items, totals)

**Gold** — `gold_invoice_match` materialized view performs:
- 3-way matching: AI-parsed invoice vs purchase order vs receiving report
- Variance calculation: price and quantity discrepancies
- Classification: `STANDARD`, `DISCREPANCY`, `UNMATCHED`, `RECEIVING_ISSUE`
- Approval routing: rules-based assignment to `AUTO_APPROVED`, `SERVICE_MANAGER`, `PARTS_DIRECTOR`, `GENERAL_MANAGER`, `EXCEPTION_REVIEW`, `RECEIVING_REVIEW`, or `PO_REQUIRED`

### 3. Invoice Processing Agent

A LangGraph agent deployed as an MLflow `ResponsesAgent` on Databricks Model Serving.

**Intent Router** directs user requests to specialized workflows:

| Intent | Action |
|--------|--------|
| `process_invoice` | Lookup → Classify → Match analysis → Submit for approval |
| `approve_invoice` | Update Lakebase status → Slack confirmation |
| `reject_invoice` | Update Lakebase status → Slack notification |
| `escalate_invoice` | Reroute to higher authority → Slack alert |
| `check_status` | Query approval history |
| `my_approvals` | List pending items for a given route |
| `general_query` | Free-form invoice Q&A |

**Tools:**
- 8 UC functions for read-only data access (invoice details, supplier search, approval status, etc.)
- 4 Python tools for write operations via Lakebase/psycopg (submit, approve, reject, escalate)
- Slack notifications routed to channel by approval route

### 4. Unity Catalog Functions

Nine SQL functions registered in `mfg_mc_se_sa.cdk`:

| Function | Source | Purpose |
|----------|--------|---------|
| `get_invoice_details` | gold_invoice_match | Single invoice lookup |
| `search_invoices_by_supplier` | gold_invoice_match | Vendor name search |
| `get_invoices_by_route` | gold_invoice_match | Filter by approval route |
| `get_supplier_performance` | gold_invoice_match | Match rate and pricing metrics |
| `get_invoice_summary` | gold_invoice_match | Grouped summary statistics |
| `get_approval_status` | Lakebase (federated) | Approval history for an invoice |
| `get_pending_approvals_for_route` | Lakebase (federated) | Pending items by role |
| `get_approval_summary` | Lakebase (federated) | Approval pipeline statistics |
| `ask_parts_invoice_agent` | Model Serving | Natural language query via `ai_query` |

### 5. Multi-Agent Supervisor

The Databricks Multi-Agent Supervisor orchestrates two specialized agents:

- **Invoice Processing Agent** — Handles structured invoice operations: processing, approvals, rejections, escalations, status checks, and supplier analytics
- **Genie Space (Invoice Approval Analytics)** — Provides ad-hoc SQL exploration over the approval pipeline and invoice match data for questions like "What's the total value of pending invoices for the parts director?" or "Show vendor discrepancy rates over time"

### 6. AI/BI Dashboard

A metric view (`invoice_metrics`) over `gold_invoice_match` powers AI/BI dashboards with:
- **Dimensions:** match status, approval route, invoice classification, vendor, vendor tier, department, invoice month
- **Measures:** invoice count, total/average value, match rate, auto-approved percentage, average price variance

---

## Deployment

The project uses **Databricks Asset Bundles (DABs)** with two targets:

| Target | Catalog | Schema |
|--------|---------|--------|
| `dev` (default) | `mfg_mc_se_sa` | `cdk` |
| `prod` | configurable | configurable |

### End-to-End Job

The orchestration job runs tasks in order:

```
generate_data → generate_pdfs → run_pipeline → create_uc_functions → log_model → deploy_agent
```

### Deploy

```bash
# Validate the bundle
databricks bundle validate -t dev

# Deploy resources
databricks bundle deploy -t dev

# Run the full pipeline
databricks bundle run parts_invoice_processing_job -t dev
```

---

## Key Technologies

| Layer | Technology |
|-------|------------|
| Data Generation | Faker, FPDF2, PySpark |
| Ingestion | Spark Declarative Pipelines, `read_files()`, Auto Loader |
| AI Enrichment | `ai_parse_document`, `ai_query` (Llama 3.3 70B) |
| Matching & Routing | SQL (materialized views, rule-based logic) |
| Agent Framework | LangGraph, MLflow `ResponsesAgent`, `UCFunctionToolkit` |
| Approval State | Lakebase Provisioned (PostgreSQL), psycopg |
| Notifications | Slack Bolt SDK, Block Kit |
| Orchestration | Databricks Multi-Agent Supervisor |
| Analytics | Genie Space, AI/BI Metric Views |
| Deployment | Databricks Asset Bundles, Model Serving |
