-- =============================================================================
-- GOLD LAYER: 3-Way Matching with AI-Parsed Invoice PDFs
-- Parts Invoice Processing Pipeline - Sunset CDJR Dealership
--
-- Invoice data sourced exclusively from AI-parsed PDFs
-- (silver_parsed_invoices_flat), joined to POs, receiving reports, and
-- suppliers for 3-way match with approval routing.
-- =============================================================================

-- 3-Way Match: AI-Parsed Invoice PDF vs Purchase Order vs Receiving Report
CREATE OR REFRESH MATERIALIZED VIEW gold_invoice_match
AS
SELECT
  regexp_extract(inv.file_path, '(INV-\\d+)\\.pdf$', 1) AS invoice_id,
  inv.invoice_number,
  inv.vendor_name,
  inv.vendor_address,
  inv.invoice_date,
  inv.due_date,
  inv.po_reference,
  inv.part_number,
  inv.part_description,
  inv.quantity AS invoice_qty,
  inv.unit_price AS invoice_unit_price,
  inv.line_total AS invoice_line_total,
  inv.subtotal AS invoice_subtotal,
  inv.tax AS invoice_tax,
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

  -- Supplier tier
  sup.vendor_tier,
  sup.supplier_id,

  -- Match analysis
  CASE
    WHEN inv.po_reference IS NULL OR inv.po_reference = '' THEN 'NO_PO_REFERENCE'
    WHEN po.po_number IS NULL THEN 'PO_NOT_FOUND'
    WHEN rr.receiving_id IS NULL THEN 'NOT_RECEIVED'
    WHEN inv.quantity != po.quantity_ordered AND ABS(inv.unit_price - po.unit_price) > 0.01 THEN 'QTY_AND_PRICE_MISMATCH'
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

  -- Approval routing
  CASE
    WHEN inv.po_reference IS NULL OR inv.po_reference = '' THEN 'PO_REQUIRED'
    WHEN po.po_number IS NULL THEN 'EXCEPTION_REVIEW'
    WHEN rr.receiving_id IS NULL THEN 'RECEIVING_REVIEW'
    WHEN inv.quantity != po.quantity_ordered OR ABS(inv.unit_price - po.unit_price) > 0.01 THEN 'EXCEPTION_REVIEW'
    WHEN rr.quantity_accepted < po.quantity_ordered THEN 'RECEIVING_REVIEW'
    WHEN inv.total_amount <= 1000 AND sup.vendor_tier = 'Preferred' THEN 'AUTO_APPROVED'
    WHEN inv.total_amount <= 500 THEN 'AUTO_APPROVED'
    WHEN inv.total_amount <= 5000 THEN 'SERVICE_MANAGER'
    WHEN inv.total_amount <= 15000 THEN 'PARTS_DIRECTOR'
    ELSE 'GENERAL_MANAGER'
  END AS approval_route,

  -- Invoice classification
  CASE
    WHEN inv.po_reference IS NULL OR inv.po_reference = '' OR po.po_number IS NULL THEN 'UNMATCHED'
    WHEN inv.quantity != po.quantity_ordered OR ABS(inv.unit_price - po.unit_price) > 0.01 THEN 'DISCREPANCY'
    WHEN rr.receiving_id IS NULL OR rr.quantity_accepted < po.quantity_ordered THEN 'RECEIVING_ISSUE'
    ELSE 'STANDARD'
  END AS invoice_classification

FROM silver_parsed_invoices_flat inv
LEFT JOIN silver_purchase_orders po
  ON inv.po_reference = po.po_number
LEFT JOIN silver_receiving_reports rr
  ON po.po_number = rr.po_number
LEFT JOIN silver_suppliers sup
  ON inv.vendor_name = sup.supplier_name
LEFT JOIN silver_emails em
  ON regexp_extract(inv.file_path, '(INV-\\d+)\\.pdf$', 1) = em.invoice_id;
