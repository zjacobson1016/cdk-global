-- =============================================================================
-- Unity Catalog Functions for Invoice Processing Agent
-- These functions serve as tools for the LangGraph agent
-- =============================================================================

-- Tool 1: Get invoice details and match status
CREATE OR REPLACE FUNCTION home_zach_jacobson.cdk.get_invoice_details(invoice_number_input STRING)
RETURNS TABLE(
  invoice_id STRING,
  invoice_number STRING,
  supplier_name STRING,
  invoice_date DATE,
  due_date STRING,
  invoice_total DECIMAL(12,2),
  po_number STRING,
  part_number STRING,
  part_name STRING,
  quantity INT,
  unit_price DECIMAL(10,2),
  match_status STRING,
  price_variance_pct DOUBLE,
  quantity_variance INT,
  approval_route STRING,
  priority STRING,
  days_until_due INT,
  vendor_tier STRING
)
LANGUAGE SQL
COMMENT 'Look up detailed invoice information including 3-way match status, approval routing, and priority. Use this when the user asks about a specific invoice by invoice number or ID.'
RETURN
  SELECT
    aq.invoice_id,
    aq.invoice_number,
    aq.supplier_name,
    im.invoice_date,
    CAST(aq.due_date AS STRING),
    aq.invoice_total,
    aq.po_number,
    im.part_number,
    im.part_name,
    im.invoice_qty AS quantity,
    im.invoice_unit_price AS unit_price,
    aq.match_status,
    aq.price_variance_pct,
    aq.quantity_variance,
    aq.approval_route,
    aq.priority,
    aq.days_until_due,
    aq.vendor_tier
  FROM home_zach_jacobson.cdk.gold_invoice_approval_queue aq
  JOIN home_zach_jacobson.cdk.gold_invoice_match im
    ON aq.invoice_id = im.invoice_id
  WHERE aq.invoice_number = invoice_number_input
     OR aq.invoice_id = invoice_number_input;


-- Tool 2: Search invoices by supplier
CREATE OR REPLACE FUNCTION home_zach_jacobson.cdk.search_invoices_by_supplier(supplier_name_input STRING)
RETURNS TABLE(
  invoice_id STRING,
  invoice_number STRING,
  supplier_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  priority STRING,
  days_until_due INT
)
LANGUAGE SQL
COMMENT 'Search for invoices from a specific supplier. Accepts partial supplier name matches. Returns invoice details with match status and approval routing.'
RETURN
  SELECT
    invoice_id,
    invoice_number,
    supplier_name,
    invoice_total,
    match_status,
    approval_route,
    priority,
    days_until_due
  FROM home_zach_jacobson.cdk.gold_invoice_approval_queue
  WHERE LOWER(supplier_name) LIKE CONCAT('%', LOWER(supplier_name_input), '%')
  ORDER BY invoice_total DESC
  LIMIT 20;


-- Tool 3: Get pending approvals by route
CREATE OR REPLACE FUNCTION home_zach_jacobson.cdk.get_pending_approvals(approval_route_input STRING)
RETURNS TABLE(
  invoice_id STRING,
  invoice_number STRING,
  supplier_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  priority STRING,
  days_until_due INT,
  invoice_classification STRING
)
LANGUAGE SQL
COMMENT 'Get invoices pending approval for a given approval route. Valid routes: AUTO_APPROVED, SERVICE_MANAGER, PARTS_DIRECTOR, GENERAL_MANAGER, EXCEPTION_REVIEW, RECEIVING_REVIEW, PO_REQUIRED, MANUAL_REVIEW. Pass "ALL" to see all non-auto-approved invoices.'
RETURN
  SELECT
    invoice_id,
    invoice_number,
    supplier_name,
    invoice_total,
    match_status,
    approval_route,
    priority,
    days_until_due,
    invoice_classification
  FROM home_zach_jacobson.cdk.gold_invoice_approval_queue
  WHERE (
    approval_route = UPPER(approval_route_input)
    OR UPPER(approval_route_input) = 'ALL'
  )
  AND approval_route != 'AUTO_APPROVED'
  ORDER BY
    CASE priority WHEN 'URGENT' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END,
    invoice_total DESC
  LIMIT 25;


-- Tool 4: Get supplier performance summary
CREATE OR REPLACE FUNCTION home_zach_jacobson.cdk.get_supplier_performance(supplier_name_input STRING)
RETURNS TABLE(
  supplier_name STRING,
  vendor_tier STRING,
  total_invoices BIGINT,
  matched_invoices BIGINT,
  discrepancy_invoices BIGINT,
  match_rate_pct DOUBLE,
  total_invoice_value DECIMAL(14,2),
  avg_invoice_value DECIMAL(12,2),
  avg_price_variance_pct DOUBLE
)
LANGUAGE SQL
COMMENT 'Get supplier performance metrics including match rate, total invoice value, and pricing accuracy. Useful for evaluating vendor reliability.'
RETURN
  SELECT
    supplier_name,
    vendor_tier,
    total_invoices,
    matched_invoices,
    discrepancy_invoices,
    match_rate_pct,
    CAST(total_invoice_value AS DECIMAL(14,2)),
    CAST(avg_invoice_value AS DECIMAL(12,2)),
    avg_price_variance_pct
  FROM home_zach_jacobson.cdk.gold_supplier_performance
  WHERE LOWER(supplier_name) LIKE CONCAT('%', LOWER(supplier_name_input), '%')
  LIMIT 10;


-- Tool 5: Get invoice processing summary/dashboard metrics
CREATE OR REPLACE FUNCTION home_zach_jacobson.cdk.get_invoice_summary()
RETURNS TABLE(
  match_status STRING,
  approval_route STRING,
  invoice_classification STRING,
  priority STRING,
  invoice_count BIGINT,
  total_value DECIMAL(14,2),
  avg_invoice_value DECIMAL(12,2)
)
LANGUAGE SQL
COMMENT 'Get an overall summary of invoice processing metrics grouped by match status, approval route, classification, and priority. Use this for high-level reporting and status overview.'
RETURN
  SELECT
    match_status,
    approval_route,
    invoice_classification,
    priority,
    invoice_count,
    CAST(total_value AS DECIMAL(14,2)),
    CAST(avg_invoice_value AS DECIMAL(12,2))
  FROM home_zach_jacobson.cdk.gold_invoice_summary
  ORDER BY invoice_count DESC;
