-- =============================================================================
-- SILVER LAYER: Validated data + AI-parsed invoice documents
-- Parts Invoice Processing Pipeline - Sunset CDJR Dealership
-- =============================================================================

-- Cleaned suppliers with validation
CREATE OR REFRESH MATERIALIZED VIEW silver_suppliers
AS
SELECT
  supplier_id,
  supplier_name,
  address,
  city,
  state,
  zip_code,
  phone,
  email,
  payment_terms,
  vendor_tier,
  _ingested_at
FROM bronze_suppliers
WHERE supplier_id IS NOT NULL
  AND supplier_name IS NOT NULL;

-- Cleaned purchase orders
CREATE OR REFRESH MATERIALIZED VIEW silver_purchase_orders
AS
SELECT
  po_number,
  supplier_id,
  part_number,
  part_name,
  CAST(quantity_ordered AS INT) AS quantity_ordered,
  CAST(unit_price AS DECIMAL(10, 2)) AS unit_price,
  CAST(total_amount AS DECIMAL(12, 2)) AS total_amount,
  CAST(order_date AS DATE) AS order_date,
  CAST(expected_delivery_date AS DATE) AS expected_delivery_date,
  status,
  department,
  ordered_by,
  _ingested_at
FROM bronze_purchase_orders
WHERE po_number IS NOT NULL
  AND quantity_ordered > 0
  AND unit_price > 0;

-- Cleaned receiving reports
CREATE OR REFRESH MATERIALIZED VIEW silver_receiving_reports
AS
SELECT
  receiving_id,
  po_number,
  supplier_id,
  part_number,
  CAST(quantity_received AS INT) AS quantity_received,
  CAST(quantity_damaged AS INT) AS quantity_damaged,
  (CAST(quantity_received AS INT) - CAST(quantity_damaged AS INT)) AS quantity_accepted,
  CAST(received_date AS DATE) AS received_date,
  received_by,
  condition,
  notes,
  _ingested_at
FROM bronze_receiving_reports
WHERE receiving_id IS NOT NULL
  AND quantity_received >= 0;

-- Cleaned invoice metadata
CREATE OR REFRESH MATERIALIZED VIEW silver_invoices
AS
SELECT
  invoice_id,
  supplier_id,
  supplier_name,
  invoice_number,
  CAST(invoice_date AS DATE) AS invoice_date,
  CAST(due_date AS DATE) AS due_date,
  po_number,
  part_number,
  part_name,
  CAST(quantity AS INT) AS quantity,
  CAST(unit_price AS DECIMAL(10, 2)) AS unit_price,
  CAST(subtotal AS DECIMAL(12, 2)) AS subtotal,
  CAST(tax AS DECIMAL(10, 2)) AS tax,
  CAST(total_amount AS DECIMAL(12, 2)) AS total_amount,
  payment_terms,
  status,
  discrepancy_type,
  department,
  _ingested_at
FROM bronze_invoices
WHERE invoice_id IS NOT NULL
  AND total_amount > 0;

-- AI-parsed invoice documents using ai_parse_document
-- Extracts structured fields from PDF binary content
CREATE OR REFRESH MATERIALIZED VIEW silver_parsed_invoice_documents
AS
SELECT
  file_path,
  file_size,
  file_modified_at,
  _ingested_at,
  ai_parse_document(
    content,
    'invoice_number STRING,
     vendor_name STRING,
     vendor_address STRING,
     invoice_date STRING,
     due_date STRING,
     payment_terms STRING,
     po_reference STRING,
     bill_to_name STRING,
     bill_to_department STRING,
     part_number STRING,
     part_description STRING,
     quantity INT,
     unit_price DOUBLE,
     line_total DOUBLE,
     subtotal DOUBLE,
     tax DOUBLE,
     total_amount DOUBLE'
  ) AS parsed
FROM bronze_invoice_documents;

-- Flattened parsed invoice documents for easy querying
CREATE OR REFRESH MATERIALIZED VIEW silver_parsed_invoices_flat
AS
SELECT
  file_path,
  parsed.invoice_number,
  parsed.vendor_name,
  parsed.vendor_address,
  CAST(parsed.invoice_date AS DATE) AS invoice_date,
  CAST(parsed.due_date AS DATE) AS due_date,
  parsed.payment_terms,
  parsed.po_reference,
  parsed.bill_to_name,
  parsed.bill_to_department AS department,
  parsed.part_number,
  parsed.part_description,
  parsed.quantity,
  CAST(parsed.unit_price AS DECIMAL(10, 2)) AS unit_price,
  CAST(parsed.line_total AS DECIMAL(12, 2)) AS line_total,
  CAST(parsed.subtotal AS DECIMAL(12, 2)) AS subtotal,
  CAST(parsed.tax AS DECIMAL(10, 2)) AS tax,
  CAST(parsed.total_amount AS DECIMAL(12, 2)) AS total_amount,
  _ingested_at
FROM silver_parsed_invoice_documents
WHERE parsed.invoice_number IS NOT NULL;

-- Cleaned emails
CREATE OR REFRESH MATERIALIZED VIEW silver_emails
AS
SELECT
  email_id,
  from_address,
  to_address,
  subject,
  body_preview,
  CAST(received_date AS DATE) AS received_date,
  has_attachment,
  attachment_filename,
  invoice_id,
  _ingested_at
FROM bronze_emails
WHERE email_id IS NOT NULL;
