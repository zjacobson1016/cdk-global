"""Create the invoice_metrics metric view over gold_invoice_match."""
import os
from databricks.sdk import WorkspaceClient

CATALOG = os.environ.get("CATALOG", "mfg_mc_se_sa")
SCHEMA = os.environ.get("SCHEMA", "cdk")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "bce0a02b2be86f1b")

METRIC_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.invoice_metrics
  WITH METRICS
  LANGUAGE YAML
  AS $$
    version: "1.1"
    comment: "Invoice processing metrics: match rates, approval routing, financial analysis by supplier, department, and time period"
    source: {CATALOG}.{SCHEMA}.gold_invoice_match

    dimensions:
      - name: Match Status
        expr: "`match_status`"
        comment: "3-way match result (MATCHED, PRICE_MISMATCH, QUANTITY_MISMATCH, etc.)"

      - name: Approval Route
        expr: "`approval_route`"
        comment: "Approval routing destination (AUTO_APPROVED, SERVICE_MANAGER, EXCEPTION_REVIEW, etc.)"

      - name: Invoice Classification
        expr: "`invoice_classification`"
        comment: "High-level invoice category (STANDARD, DISCREPANCY, UNMATCHED, RECEIVING_ISSUE)"

      - name: Vendor Name
        expr: "`vendor_name`"
        comment: "Supplier name from AI-parsed invoice PDF"

      - name: Vendor Tier
        expr: "`vendor_tier`"
        comment: "Supplier tier (Preferred, Standard, Probationary)"

      - name: Department
        expr: "`department`"
        comment: "Dealership department (Service, Body Shop, Parts Counter, etc.)"

      - name: Invoice Month
        expr: "DATE_TRUNC('MONTH', `invoice_date`)"
        comment: "Invoice date truncated to month"

      - name: Invoice Date
        expr: "`invoice_date`"
        comment: "Invoice date"

    measures:
      - name: Total Invoices
        expr: "COUNT(*)"
        comment: "Count of invoices"

      - name: Total Invoice Value
        expr: "SUM(`invoice_total`)"
        comment: "Sum of all invoice totals"

      - name: Average Invoice Value
        expr: "AVG(`invoice_total`)"
        comment: "Average invoice total amount"

      - name: Matched Invoices
        expr: "COUNT(CASE WHEN `match_status` = 'MATCHED' THEN 1 END)"
        comment: "Count of fully matched invoices"

      - name: Discrepancy Invoices
        expr: "COUNT(CASE WHEN `match_status` != 'MATCHED' THEN 1 END)"
        comment: "Count of invoices with discrepancies"

      - name: Match Rate
        expr: "COUNT(CASE WHEN `match_status` = 'MATCHED' THEN 1 END) * 100.0 / COUNT(*)"
        comment: "Percentage of invoices that fully matched"

      - name: Avg Price Variance Pct
        expr: "AVG(ABS(COALESCE(`price_variance_pct`, 0)))"
        comment: "Average absolute price variance percentage"

      - name: Auto Approved Count
        expr: "COUNT(CASE WHEN `approval_route` = 'AUTO_APPROVED' THEN 1 END)"
        comment: "Count of auto-approved invoices"

      - name: Exception Review Count
        expr: "COUNT(CASE WHEN `approval_route` = 'EXCEPTION_REVIEW' THEN 1 END)"
        comment: "Count of invoices requiring exception review"

      - name: Max Invoice Value
        expr: "MAX(`invoice_total`)"
        comment: "Largest single invoice amount"

      - name: Total Tax
        expr: "SUM(`invoice_tax`)"
        comment: "Sum of all invoice tax amounts"
  $$
"""

if __name__ == "__main__":
    w = WorkspaceClient()

    print(f"Creating metric view {CATALOG}.{SCHEMA}.invoice_metrics...")
    result = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID,
        statement=METRIC_VIEW_SQL,
        catalog=CATALOG,
        schema=SCHEMA,
    )

    if result.status and result.status.state.value == "SUCCEEDED":
        print(f"Metric view {CATALOG}.{SCHEMA}.invoice_metrics created successfully.")
    else:
        error = result.status.error if result.status else "Unknown error"
        print(f"Failed to create metric view: {error}")
        raise SystemExit(1)
