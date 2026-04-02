-- =============================================================================
-- BRONZE LAYER: Raw data ingestion from Unity Catalog Volumes
-- Service Advisor Agent Pipeline - CDK Global Dealership
-- Pipeline config variables: ${catalog}, ${schema}
-- =============================================================================

-- Customer master data
CREATE OR REFRESH STREAMING TABLE bronze_customers
CLUSTER BY (customer_id)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/customers/',
  format => 'parquet'
);

-- Vehicle inventory
CREATE OR REFRESH STREAMING TABLE bronze_vehicles
CLUSTER BY (customer_id)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/vehicles/',
  format => 'parquet'
);

-- Service appointments
CREATE OR REFRESH STREAMING TABLE bronze_appointments
CLUSTER BY (appointment_date)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/appointments/',
  format => 'parquet'
);

-- Customer lifetime value scores
CREATE OR REFRESH STREAMING TABLE bronze_clv
CLUSTER BY (customer_id)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/customer_lifetime_value/',
  format => 'parquet'
);

-- Technician master data
CREATE OR REFRESH STREAMING TABLE bronze_technicians
CLUSTER BY (tech_id)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/technicians/',
  format => 'parquet'
);

-- Technician performance metrics
CREATE OR REFRESH STREAMING TABLE bronze_tech_performance
CLUSTER BY (tech_id)
AS
SELECT
  *,
  current_timestamp() AS _ingested_at,
  _metadata.file_path AS _source_file
FROM STREAM read_files(
  '/Volumes/${catalog}/${schema}/raw_data/technician_performance/',
  format => 'parquet'
);
