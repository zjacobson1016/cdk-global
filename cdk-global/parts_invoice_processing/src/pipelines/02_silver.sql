-- =============================================================================
-- SILVER LAYER: Validated data + AI-parsed invoice documents
-- Parts Invoice Processing Pipeline - Sunset CDJR Dealership
--
-- Document parsing uses a two-step approach:
--   1. ai_parse_document(content) → VARIANT with document elements
--   2. ai_query(..., responseFormat => ...) → structured invoice fields
-- =============================================================================

-- Cleaned suppliers with validation
CREATE OR REFRESH STREAMING TABLE silver_suppliers
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
FROM STREAM(bronze_suppliers)
WHERE supplier_id IS NOT NULL
  AND supplier_name IS NOT NULL;

-- Cleaned purchase orders
CREATE OR REFRESH STREAMING TABLE silver_purchase_orders
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
FROM STREAM(bronze_purchase_orders)
WHERE po_number IS NOT NULL
  AND quantity_ordered > 0
  AND unit_price > 0;

-- Cleaned receiving reports
CREATE OR REFRESH STREAMING TABLE silver_receiving_reports
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
FROM STREAM(bronze_receiving_reports)
WHERE receiving_id IS NOT NULL
  AND quantity_received >= 0;

-- =============================================================================
-- STEP 1: Parse PDF binary content into structured document elements
-- ai_parse_document returns a VARIANT with:
--   document.pages[]    → page metadata
--   document.elements[] → extracted content (type, content, bbox, description)
--   error_status[]      → error details per page
--   metadata            → file and schema version info
-- =============================================================================
CREATE OR REFRESH STREAMING TABLE silver_parsed_invoice_documents
AS
SELECT
  file_path,
  file_size,
  file_modified_at,
  _ingested_at,
  ai_parse_document(content, map('version', '2.0')) AS parsed_doc,
  concat_ws(
    '\n',
    transform(
      CAST(ai_parse_document(content, map('version', '2.0')):document:elements AS ARRAY<VARIANT>),
      el -> el:content::STRING
    )
  ) AS extracted_text
FROM STREAM(bronze_invoice_documents);

-- =============================================================================
-- STEP 2: Extract structured invoice fields from parsed text using ai_query
-- Uses responseFormat to force structured JSON output from the LLM
-- =============================================================================
CREATE OR REFRESH STREAMING TABLE silver_parsed_invoices_flat
AS
SELECT
  file_path,
  _ingested_at,
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
  CAST(regexp_replace(parsed.quantity, '[^0-9\\-]', '') AS INT) AS quantity,
  CAST(regexp_replace(parsed.unit_price, '[^0-9.\\-]', '') AS DECIMAL(10, 2)) AS unit_price,
  CAST(regexp_replace(parsed.line_total, '[^0-9.\\-]', '') AS DECIMAL(12, 2)) AS line_total,
  CAST(regexp_replace(parsed.subtotal, '[^0-9.\\-]', '') AS DECIMAL(12, 2)) AS subtotal,
  CAST(regexp_replace(parsed.tax, '[^0-9.\\-]', '') AS DECIMAL(10, 2)) AS tax,
  CAST(regexp_replace(parsed.total_amount, '[^0-9.\\-]', '') AS DECIMAL(12, 2)) AS total_amount
FROM (
  SELECT
    file_path,
    _ingested_at,
    from_json(
      ai_query(
        'databricks-meta-llama-3-3-70b-instruct',
        CONCAT(
          'Extract structured invoice data from the following document text. '
          'Return all fields exactly as they appear in the document.\n\n',
          extracted_text
        ),
        responseFormat => '{"type": "json_schema", "json_schema": {"name": "invoice_extraction", "schema": {"type": "object", "properties": {"invoice_number": {"type": "string"}, "vendor_name": {"type": "string"}, "vendor_address": {"type": "string"}, "invoice_date": {"type": "string"}, "due_date": {"type": "string"}, "payment_terms": {"type": "string"}, "po_reference": {"type": "string"}, "bill_to_name": {"type": "string"}, "bill_to_department": {"type": "string"}, "part_number": {"type": "string"}, "part_description": {"type": "string"}, "quantity": {"type": "string"}, "unit_price": {"type": "string"}, "line_total": {"type": "string"}, "subtotal": {"type": "string"}, "tax": {"type": "string"}, "total_amount": {"type": "string"}}, "required": ["invoice_number", "vendor_name", "vendor_address", "invoice_date", "due_date", "payment_terms", "po_reference", "bill_to_name", "bill_to_department", "part_number", "part_description", "quantity", "unit_price", "line_total", "subtotal", "tax", "total_amount"]}, "strict": true}}',
        modelParameters => named_struct('temperature', CAST(0.0 AS DOUBLE), 'max_tokens', 1024)
      ),
      'STRUCT<invoice_number: STRING, vendor_name: STRING, vendor_address: STRING, invoice_date: STRING, due_date: STRING, payment_terms: STRING, po_reference: STRING, bill_to_name: STRING, bill_to_department: STRING, part_number: STRING, part_description: STRING, quantity: STRING, unit_price: STRING, line_total: STRING, subtotal: STRING, tax: STRING, total_amount: STRING>'
    ) AS parsed
  FROM STREAM(silver_parsed_invoice_documents)
  WHERE extracted_text IS NOT NULL
);

-- Cleaned emails
CREATE OR REFRESH STREAMING TABLE silver_emails
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
FROM STREAM(bronze_emails)
WHERE email_id IS NOT NULL;
