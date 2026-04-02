-- =============================================================================
-- SILVER LAYER: Validated and typed data
-- Service Advisor Agent Pipeline - CDK Global Dealership
-- =============================================================================

-- Cleaned customers with validation
CREATE OR REFRESH STREAMING TABLE silver_customers
AS
SELECT
  customer_id,
  first_name,
  last_name,
  CONCAT(first_name, ' ', last_name) AS full_name,
  phone,
  email,
  address,
  city,
  state,
  zip_code,
  preferred_contact,
  loyalty_tier,
  CAST(customer_since AS DATE) AS customer_since,
  _ingested_at
FROM STREAM(bronze_customers)
WHERE customer_id IS NOT NULL
  AND first_name IS NOT NULL
  AND last_name IS NOT NULL;

-- Cleaned vehicles
CREATE OR REFRESH STREAMING TABLE silver_vehicles
AS
SELECT
  vehicle_id,
  customer_id,
  vin,
  CAST(year AS INT) AS year,
  make,
  model,
  trim,
  CAST(mileage AS INT) AS mileage,
  CAST(last_service_date AS DATE) AS last_service_date,
  CONCAT(CAST(year AS STRING), ' ', make, ' ', model, ' ', trim) AS vehicle_description,
  _ingested_at
FROM STREAM(bronze_vehicles)
WHERE vehicle_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND vin IS NOT NULL;

-- Cleaned appointments
CREATE OR REFRESH STREAMING TABLE silver_appointments
AS
SELECT
  appointment_id,
  customer_id,
  vehicle_id,
  CAST(appointment_date AS DATE) AS appointment_date,
  appointment_time,
  service_type,
  CAST(estimated_duration_mins AS INT) AS estimated_duration_mins,
  status,
  advisor_notes,
  _ingested_at
FROM STREAM(bronze_appointments)
WHERE appointment_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND vehicle_id IS NOT NULL;

-- Cleaned customer lifetime value
CREATE OR REFRESH STREAMING TABLE silver_clv
AS
SELECT
  customer_id,
  CAST(total_spend AS DECIMAL(12, 2)) AS total_spend,
  CAST(visit_count AS INT) AS visit_count,
  CAST(avg_repair_order_value AS DECIMAL(10, 2)) AS avg_repair_order_value,
  CAST(months_as_customer AS INT) AS months_as_customer,
  CAST(referral_count AS INT) AS referral_count,
  CAST(clv_score AS DECIMAL(8, 2)) AS clv_score,
  clv_tier,
  _ingested_at
FROM STREAM(bronze_clv)
WHERE customer_id IS NOT NULL
  AND clv_score >= 0;

-- Cleaned technicians
CREATE OR REFRESH STREAMING TABLE silver_technicians
AS
SELECT
  tech_id,
  first_name,
  last_name,
  CONCAT(first_name, ' ', last_name) AS full_name,
  certifications,
  specialization,
  CAST(hire_date AS DATE) AS hire_date,
  shift,
  _ingested_at
FROM STREAM(bronze_technicians)
WHERE tech_id IS NOT NULL
  AND first_name IS NOT NULL;

-- Cleaned technician performance
CREATE OR REFRESH STREAMING TABLE silver_tech_performance
AS
SELECT
  tech_id,
  CAST(total_jobs AS INT) AS total_jobs,
  CAST(avg_completion_time_mins AS DECIMAL(6, 1)) AS avg_completion_time_mins,
  CAST(reopen_rate_pct AS DECIMAL(5, 1)) AS reopen_rate_pct,
  CAST(customer_satisfaction_score AS DECIMAL(3, 2)) AS customer_satisfaction_score,
  CAST(first_time_fix_rate_pct AS DECIMAL(5, 1)) AS first_time_fix_rate_pct,
  _ingested_at
FROM STREAM(bronze_tech_performance)
WHERE tech_id IS NOT NULL
  AND total_jobs > 0;
