-- =============================================================================
-- BRONZE LAYER: Raw data ingestion from Unity Catalog Volumes
-- Parts Invoice Processing Pipeline - Sunset CDJR Dealership
-- Pipeline config variables: ${catalog}, ${schema}
-- =============================================================================

-- Suppliers master data
CREATE OR REFRESH STREAMING TABLE bronze_suppliers
CLUSTER BY (supplier_id)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/suppliers/',
  format => 'parquet'
);

-- Purchase orders
CREATE OR REFRESH STREAMING TABLE bronze_purchase_orders
CLUSTER BY (order_date)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/purchase_orders/',
  format => 'parquet'
);

-- Receiving reports
CREATE OR REFRESH STREAMING TABLE bronze_receiving_reports
CLUSTER BY (received_date)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/receiving_reports/',
  format => 'parquet'
);

-- Invoice metadata (structured)
CREATE OR REFRESH STREAMING TABLE bronze_invoices
CLUSTER BY (invoice_date)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/invoices/',
  format => 'parquet'
);

-- Email metadata
CREATE OR REFRESH STREAMING TABLE bronze_emails
CLUSTER BY (received_date)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/emails/',
  format => 'parquet'
);

-- Invoice PDF documents (binary content for ai_parse_document)
CREATE OR REFRESH STREAMING TABLE bronze_invoice_documents
AS
SELECT
  path AS file_path,
  content,
  length AS file_size,
  modificationTime AS file_modified_at,
  current_timestamp() AS _ingested_at
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/invoice_pdfs/',
  format => 'binaryFile'
);
