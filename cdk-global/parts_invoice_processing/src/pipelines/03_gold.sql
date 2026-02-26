-- =============================================================================
-- GOLD LAYER: 3-Way Matching, Classification, and Approval Routing
-- Parts Invoice Processing Pipeline - Sunset CDJR Dealership
-- =============================================================================

-- 3-Way Match: Invoice vs Purchase Order vs Receiving Report
CREATE OR REFRESH MATERIALIZED VIEW gold_invoice_match
AS
SELECT
  inv.invoice_id,
  inv.invoice_number,
  inv.supplier_id,
  inv.supplier_name,
  inv.invoice_date,
  inv.due_date,
  inv.po_number AS invoice_po_ref,
  inv.part_number,
  inv.part_name,
  inv.quantity AS invoice_qty,
  inv.unit_price AS invoice_unit_price,
  inv.total_amount AS invoice_total,
  inv.payment_terms,
  inv.department,

  -- PO details
  po.po_number,
  po.quantity_ordered AS po_qty,
  po.unit_price AS po_unit_price,
  po.total_amount AS po_total,
  po.order_date AS po_date,
  po.status AS po_status,

  -- Receiving report details
  rr.receiving_id,
  rr.quantity_received,
  rr.quantity_damaged,
  rr.quantity_accepted,
  rr.received_date,
  rr.condition AS receiving_condition,

  -- Match analysis
  CASE
    WHEN inv.po_number IS NULL OR inv.po_number = '' THEN 'NO_PO_REFERENCE'
    WHEN po.po_number IS NULL THEN 'PO_NOT_FOUND'
    WHEN rr.receiving_id IS NULL THEN 'NOT_RECEIVED'
    WHEN inv.quantity != po.quantity_ordered AND inv.unit_price != po.unit_price THEN 'QTY_AND_PRICE_MISMATCH'
    WHEN inv.quantity != po.quantity_ordered THEN 'QUANTITY_MISMATCH'
    WHEN ABS(inv.unit_price - po.unit_price) > 0.01 THEN 'PRICE_MISMATCH'
    WHEN rr.quantity_accepted < po.quantity_ordered THEN 'PARTIAL_RECEIPT'
    ELSE 'MATCHED'
  END AS match_status,

  -- Price variance
  CASE
    WHEN po.unit_price IS NOT NULL AND po.unit_price > 0
    THEN ROUND(((inv.unit_price - po.unit_price) / po.unit_price) * 100, 2)
    ELSE NULL
  END AS price_variance_pct,

  -- Quantity variance
  CASE
    WHEN po.quantity_ordered IS NOT NULL AND po.quantity_ordered > 0
    THEN inv.quantity - po.quantity_ordered
    ELSE NULL
  END AS quantity_variance,

  -- Supplier tier
  sup.vendor_tier

FROM silver_invoices inv
LEFT JOIN silver_purchase_orders po
  ON inv.po_number = po.po_number
LEFT JOIN silver_receiving_reports rr
  ON po.po_number = rr.po_number
LEFT JOIN silver_suppliers sup
  ON inv.supplier_id = sup.supplier_id;


-- Approval routing logic based on match status, amount, and vendor tier
CREATE OR REFRESH MATERIALIZED VIEW gold_invoice_approval_queue
AS
SELECT
  invoice_id,
  invoice_number,
  supplier_name,
  vendor_tier,
  invoice_date,
  due_date,
  invoice_total,
  match_status,
  price_variance_pct,
  quantity_variance,
  department,
  po_number,

  -- Auto-approve if matched, under $1000, and preferred vendor
  CASE
    WHEN match_status = 'MATCHED' AND invoice_total <= 1000 AND vendor_tier = 'Preferred'
      THEN 'AUTO_APPROVED'
    WHEN match_status = 'MATCHED' AND invoice_total <= 500
      THEN 'AUTO_APPROVED'
    WHEN match_status = 'MATCHED' AND invoice_total <= 5000
      THEN 'SERVICE_MANAGER'
    WHEN match_status = 'MATCHED' AND invoice_total <= 15000
      THEN 'PARTS_DIRECTOR'
    WHEN match_status = 'MATCHED'
      THEN 'GENERAL_MANAGER'
    WHEN match_status IN ('PRICE_MISMATCH', 'QUANTITY_MISMATCH', 'QTY_AND_PRICE_MISMATCH')
      THEN 'EXCEPTION_REVIEW'
    WHEN match_status = 'PARTIAL_RECEIPT'
      THEN 'RECEIVING_REVIEW'
    WHEN match_status = 'NO_PO_REFERENCE'
      THEN 'PO_REQUIRED'
    WHEN match_status = 'PO_NOT_FOUND'
      THEN 'EXCEPTION_REVIEW'
    WHEN match_status = 'NOT_RECEIVED'
      THEN 'RECEIVING_REVIEW'
    ELSE 'MANUAL_REVIEW'
  END AS approval_route,

  -- Priority based on due date proximity and amount
  CASE
    WHEN DATEDIFF(due_date, current_date()) <= 3 THEN 'URGENT'
    WHEN DATEDIFF(due_date, current_date()) <= 7 THEN 'HIGH'
    WHEN DATEDIFF(due_date, current_date()) <= 14 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS priority,

  -- Days until due
  DATEDIFF(due_date, current_date()) AS days_until_due,

  -- Classification
  CASE
    WHEN match_status = 'MATCHED' THEN 'STANDARD'
    WHEN match_status IN ('PRICE_MISMATCH', 'QUANTITY_MISMATCH', 'QTY_AND_PRICE_MISMATCH') THEN 'DISCREPANCY'
    WHEN match_status IN ('NO_PO_REFERENCE', 'PO_NOT_FOUND') THEN 'UNMATCHED'
    WHEN match_status IN ('PARTIAL_RECEIPT', 'NOT_RECEIVED') THEN 'RECEIVING_ISSUE'
    ELSE 'OTHER'
  END AS invoice_classification

FROM gold_invoice_match;


-- Summary metrics for dashboard / agent queries
CREATE OR REFRESH MATERIALIZED VIEW gold_invoice_summary
AS
SELECT
  match_status,
  approval_route,
  invoice_classification,
  priority,
  COUNT(*) AS invoice_count,
  SUM(invoice_total) AS total_value,
  AVG(invoice_total) AS avg_invoice_value,
  MIN(days_until_due) AS min_days_until_due
FROM gold_invoice_approval_queue
GROUP BY match_status, approval_route, invoice_classification, priority;


-- Supplier performance metrics
CREATE OR REFRESH MATERIALIZED VIEW gold_supplier_performance
AS
SELECT
  im.supplier_id,
  im.supplier_name,
  im.vendor_tier,
  COUNT(*) AS total_invoices,
  SUM(CASE WHEN im.match_status = 'MATCHED' THEN 1 ELSE 0 END) AS matched_invoices,
  SUM(CASE WHEN im.match_status != 'MATCHED' THEN 1 ELSE 0 END) AS discrepancy_invoices,
  ROUND(
    SUM(CASE WHEN im.match_status = 'MATCHED' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1
  ) AS match_rate_pct,
  SUM(im.invoice_total) AS total_invoice_value,
  AVG(im.invoice_total) AS avg_invoice_value,
  AVG(ABS(COALESCE(im.price_variance_pct, 0))) AS avg_price_variance_pct
FROM gold_invoice_match im
GROUP BY im.supplier_id, im.supplier_name, im.vendor_tier;
