"""Register Unity Catalog SQL functions for the Invoice Processing Agent.

Read-only query functions. Write operations (approve, reject, escalate)
are handled by Python tools in the agent via Lakebase (psycopg).
"""
from databricks.connect import DatabricksSession

CATALOG = "mfg_mc_se_sa"
SCHEMA = "cdk"

# With explicit profile
spark = DatabricksSession.builder.profile("group-demo").serverless().getOrCreate()

# ── Tool 1: Get invoice details and match status ────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_invoice_details(invoice_number_input STRING)
RETURNS TABLE(
  invoice_id STRING,
  invoice_number STRING,
  vendor_name STRING,
  invoice_date DATE,
  due_date STRING,
  invoice_total DECIMAL(12,2),
  po_number STRING,
  part_number STRING,
  part_description STRING,
  quantity INT,
  unit_price DECIMAL(10,2),
  match_status STRING,
  price_variance_pct DOUBLE,
  quantity_variance INT,
  approval_route STRING,
  invoice_classification STRING,
  vendor_tier STRING,
  department STRING,
  received_via_email BOOLEAN
)
LANGUAGE SQL
COMMENT 'Look up detailed invoice information including 3-way match status, approval routing, and classification. Use this when the user asks about a specific invoice by invoice number or ID.'
RETURN
  SELECT
    a.invoice_id,
    a.invoice_number,
    a.vendor_name,
    a.invoice_date,
    CAST(a.due_date AS STRING),
    a.invoice_total,
    a.po_number,
    a.part_number,
    a.part_description,
    a.invoice_qty AS quantity,
    a.invoice_unit_price AS unit_price,
    a.match_status,
    a.price_variance_pct,
    a.quantity_variance,
    a.approval_route,
    a.invoice_classification,
    a.vendor_tier,
    a.department,
    a.received_via_email
  FROM {CATALOG}.{SCHEMA}.gold_invoice_match_sync a
  LEFT JOIN cdk_invoicing.public.invoice_approval_log b
    ON a.invoice_id = b.invoice_id
  WHERE b.invoice_id IS NULL
    AND (a.invoice_number = invoice_number_input
     OR a.invoice_id = invoice_number_input)
""")
print("1/8 get_invoice_details")


# ── Tool 2: Search invoices by supplier ─────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.search_invoices_by_supplier(supplier_name_input STRING)
RETURNS TABLE(
  invoice_id STRING,
  invoice_number STRING,
  vendor_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  invoice_classification STRING,
  vendor_tier STRING
)
LANGUAGE SQL
COMMENT 'Search for invoices from a specific supplier. Accepts partial supplier name matches. Returns invoice details with match status and approval routing.'
RETURN
  SELECT
    a.invoice_id,
    a.invoice_number,
    a.vendor_name,
    a.invoice_total,
    a.match_status,
    a.approval_route,
    a.invoice_classification,
    a.vendor_tier
  FROM {CATALOG}.{SCHEMA}.gold_invoice_match_sync a
  LEFT JOIN cdk_invoicing.public.invoice_approval_log b
    ON a.invoice_id = b.invoice_id
  WHERE b.invoice_id IS NULL
    AND LOWER(a.vendor_name) LIKE CONCAT('%', LOWER(supplier_name_input), '%')
  ORDER BY a.invoice_total DESC
  LIMIT 20
""")
print("2/8 search_invoices_by_supplier")


# ── Tool 3: Get invoices by approval route ──────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_invoices_by_route(approval_route_input STRING)
RETURNS TABLE(
  invoice_id STRING,
  invoice_number STRING,
  vendor_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  invoice_classification STRING,
  vendor_tier STRING,
  department STRING
)
LANGUAGE SQL
COMMENT 'Get invoices assigned to a given approval route. Valid routes: AUTO_APPROVED, SERVICE_MANAGER, PARTS_DIRECTOR, GENERAL_MANAGER, EXCEPTION_REVIEW, RECEIVING_REVIEW, PO_REQUIRED. Pass "ALL" to see all non-auto-approved invoices.'
RETURN
  SELECT
    a.invoice_id,
    a.invoice_number,
    a.vendor_name,
    a.invoice_total,
    a.match_status,
    a.approval_route,
    a.invoice_classification,
    a.vendor_tier,
    a.department
  FROM {CATALOG}.{SCHEMA}.gold_invoice_match_sync a
  LEFT JOIN cdk_invoicing.public.invoice_approval_log b
    ON a.invoice_id = b.invoice_id
  WHERE b.invoice_id IS NULL
    AND (
      a.approval_route = UPPER(approval_route_input)
      OR UPPER(approval_route_input) = 'ALL'
    )
    AND a.approval_route != 'AUTO_APPROVED'
  ORDER BY a.invoice_total DESC
  LIMIT 25
""")
print("3/8 get_invoices_by_route")


# ── Tool 4: Get supplier performance summary ────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_supplier_performance(supplier_name_input STRING)
RETURNS TABLE(
  vendor_name STRING,
  vendor_tier STRING,
  total_invoices BIGINT,
  matched_invoices BIGINT,
  discrepancy_invoices BIGINT,
  match_rate_pct DOUBLE,
  total_invoice_value DOUBLE,
  avg_invoice_value DOUBLE,
  avg_price_variance_pct DOUBLE
)
LANGUAGE SQL
COMMENT 'Get supplier performance metrics including match rate, total invoice value, and pricing accuracy. Useful for evaluating vendor reliability.'
RETURN
  SELECT
    a.vendor_name,
    a.vendor_tier,
    COUNT(*) AS total_invoices,
    COUNT(CASE WHEN a.match_status = 'MATCHED' THEN 1 END) AS matched_invoices,
    COUNT(CASE WHEN a.match_status != 'MATCHED' THEN 1 END) AS discrepancy_invoices,
    ROUND(COUNT(CASE WHEN a.match_status = 'MATCHED' THEN 1 END) * 100.0 / COUNT(*), 2) AS match_rate_pct,
    CAST(SUM(a.invoice_total) AS DOUBLE) AS total_invoice_value,
    CAST(AVG(a.invoice_total) AS DOUBLE) AS avg_invoice_value,
    ROUND(AVG(ABS(COALESCE(a.price_variance_pct, 0))), 2) AS avg_price_variance_pct
  FROM {CATALOG}.{SCHEMA}.gold_invoice_match_sync a
  LEFT JOIN cdk_invoicing.public.invoice_approval_log b
    ON a.invoice_id = b.invoice_id
  WHERE b.invoice_id IS NULL
    AND LOWER(a.vendor_name) LIKE CONCAT('%', LOWER(supplier_name_input), '%')
  GROUP BY a.vendor_name, a.vendor_tier
  LIMIT 10
""")
print("4/8 get_supplier_performance")


# ── Tool 5: Get invoice processing summary ──────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_invoice_summary()
RETURNS TABLE(
  match_status STRING,
  approval_route STRING,
  invoice_classification STRING,
  invoice_count BIGINT,
  total_value DOUBLE,
  avg_invoice_value DOUBLE
)
LANGUAGE SQL
COMMENT 'Get an overall summary of invoice processing metrics grouped by match status, approval route, and classification. Use this for high-level reporting and status overview.'
RETURN
  SELECT
    a.match_status,
    a.approval_route,
    a.invoice_classification,
    COUNT(*) AS invoice_count,
    CAST(SUM(a.invoice_total) AS DOUBLE) AS total_value,
    CAST(AVG(a.invoice_total) AS DOUBLE) AS avg_invoice_value
  FROM {CATALOG}.{SCHEMA}.gold_invoice_match_sync a
  LEFT JOIN cdk_invoicing.public.invoice_approval_log b
    ON a.invoice_id = b.invoice_id
  WHERE b.invoice_id IS NULL
  GROUP BY a.match_status, a.approval_route, a.invoice_classification
  ORDER BY invoice_count DESC
""")
print("5/8 get_invoice_summary")


# ═════════════════════════════════════════════════════════════════════════════
# APPROVAL WORKFLOW READ FUNCTIONS (query invoice_approval_log)
# ═════════════════════════════════════════════════════════════════════════════

# ── Tool 6: Get approval status for a specific invoice ──────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_approval_status(invoice_id_input STRING)
RETURNS TABLE(
  approval_id STRING,
  invoice_id STRING,
  invoice_number STRING,
  vendor_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  assigned_to STRING,
  status STRING,
  submitted_at TIMESTAMP,
  acted_on_at TIMESTAMP,
  acted_by STRING,
  rejection_reason STRING,
  escalated_to STRING,
  notes STRING
)
LANGUAGE SQL
COMMENT 'Get the full approval history for a specific invoice. Shows all approval actions (submissions, approvals, rejections, escalations) in chronological order. Use when the user asks about the status of an invoice approval.'
RETURN
  SELECT
    approval_id,
    invoice_id,
    invoice_number,
    vendor_name,
    invoice_total,
    match_status,
    approval_route,
    assigned_to,
    status,
    submitted_at,
    acted_on_at,
    acted_by,
    rejection_reason,
    escalated_to,
    notes
  FROM cdk_invoicing.public.invoice_approval_log
  WHERE invoice_id = invoice_id_input
     OR invoice_number = invoice_id_input
  ORDER BY submitted_at DESC
""")
print("6/8 get_approval_status")


# ── Tool 7: Get pending approvals for a given route/role ────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_pending_approvals_for_route(approval_route_input STRING)
RETURNS TABLE(
  approval_id STRING,
  invoice_id STRING,
  invoice_number STRING,
  vendor_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  submitted_at TIMESTAMP,
  hours_pending DOUBLE
)
LANGUAGE SQL
COMMENT 'Get all invoices with PENDING approval status for a given route. Use when an approver asks "what do I need to approve?" Valid routes: SERVICE_MANAGER, PARTS_DIRECTOR, GENERAL_MANAGER, EXCEPTION_REVIEW, RECEIVING_REVIEW. Pass "ALL" for all pending.'
RETURN
  SELECT
    approval_id,
    invoice_id,
    invoice_number,
    vendor_name,
    invoice_total,
    match_status,
    approval_route,
    submitted_at,
    ROUND((unix_timestamp(current_timestamp()) - unix_timestamp(submitted_at)) / 3600.0, 1) AS hours_pending
  FROM cdk_invoicing.public.invoice_approval_log
  WHERE status = 'PENDING'
    AND (
      approval_route = UPPER(approval_route_input)
      OR UPPER(approval_route_input) = 'ALL'
    )
  ORDER BY submitted_at ASC
  LIMIT 25
""")
print("7/8 get_pending_approvals_for_route")


# ── Tool 8: Approval pipeline summary ──────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_approval_summary()
RETURNS TABLE(
  status STRING,
  approval_route STRING,
  request_count BIGINT,
  total_value DOUBLE,
  avg_hours_pending DOUBLE,
  oldest_request TIMESTAMP
)
LANGUAGE SQL
COMMENT 'Aggregate statistics on the approval pipeline: counts by status and route, total value, and average wait time. Use for operational dashboards and identifying bottlenecks.'
RETURN
  SELECT
    status,
    approval_route,
    COUNT(*) AS request_count,
    CAST(SUM(invoice_total) AS DOUBLE) AS total_value,
    ROUND(AVG(
      CASE WHEN status = 'PENDING'
        THEN (unix_timestamp(current_timestamp()) - unix_timestamp(submitted_at)) / 3600.0
        ELSE (unix_timestamp(acted_on_at) - unix_timestamp(submitted_at)) / 3600.0
      END
    ), 1) AS avg_hours_pending,
    MIN(submitted_at) AS oldest_request
  FROM cdk_invoicing.public.invoice_approval_log
  GROUP BY status, approval_route
  ORDER BY
    CASE status WHEN 'PENDING' THEN 1 WHEN 'ESCALATED' THEN 2 ELSE 3 END,
    request_count DESC
""")
print("8/9 get_approval_summary")


# ═════════════════════════════════════════════════════════════════════════════
# AGENT ENDPOINT QUERY FUNCTION
# ═════════════════════════════════════════════════════════════════════════════

# ── Tool 9: Query the parts invoice agent endpoint ───────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.ask_parts_invoice_agent(question STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Ask a natural-language question to the Parts Invoice Processing Agent. The agent can look up invoices, check approval status, search by supplier, and more. Returns the agent response as a string.'
RETURN
  SELECT ai_query(
    'agents_mfg_mc_se_sa-cdk-parts_invoice_agent', question
    ) AS response
""")
print("9/9 ask_parts_invoice_agent")

print(f"\nAll 9 UC functions created in {CATALOG}.{SCHEMA}")
