-- =============================================================================
-- GOLD LAYER: Customer appointment profiles and technician rankings
-- Service Advisor Agent Pipeline - CDK Global Dealership
--
-- Two materialized views:
--   1. gold_daily_appointment_profiles — full customer context per appointment
--   2. gold_technician_rankings — ranked technicians with composite scores
-- =============================================================================

-- Full customer profile per appointment (joins appointments + customers + vehicles + CLV)
CREATE OR REFRESH MATERIALIZED VIEW gold_daily_appointment_profiles
AS
SELECT
  appt.appointment_id,
  appt.appointment_date,
  appt.appointment_time,
  appt.service_type,
  appt.estimated_duration_mins,
  appt.status AS appointment_status,
  appt.advisor_notes,

  -- Customer details
  cust.customer_id,
  cust.full_name AS customer_name,
  cust.phone AS customer_phone,
  cust.email AS customer_email,
  cust.preferred_contact,
  cust.loyalty_tier,
  cust.customer_since,

  -- Vehicle details
  veh.vehicle_id,
  veh.vehicle_description,
  veh.vin,
  veh.year AS vehicle_year,
  veh.make,
  veh.model,
  veh.mileage,
  veh.last_service_date,

  -- CLV metrics
  clv.total_spend,
  clv.visit_count,
  clv.avg_repair_order_value,
  clv.months_as_customer,
  clv.referral_count,
  clv.clv_score,
  clv.clv_tier

FROM silver_appointments appt
INNER JOIN silver_customers cust
  ON appt.customer_id = cust.customer_id
INNER JOIN silver_vehicles veh
  ON appt.vehicle_id = veh.vehicle_id
LEFT JOIN silver_clv clv
  ON appt.customer_id = clv.customer_id;


-- Technician rankings with composite performance score
CREATE OR REFRESH MATERIALIZED VIEW gold_technician_rankings
AS
SELECT
  tech.tech_id,
  tech.full_name AS technician_name,
  tech.certifications,
  tech.specialization,
  tech.hire_date,
  tech.shift,

  -- Raw performance metrics
  perf.total_jobs,
  perf.avg_completion_time_mins,
  perf.reopen_rate_pct,
  perf.customer_satisfaction_score,
  perf.first_time_fix_rate_pct,

  -- Composite tech score:
  --   CSAT (0-5 normalized to 0-100) * 0.30
  --   + First-time fix rate * 0.30
  --   + (100 - reopen_rate) * 0.20
  --   + Speed score (inverse of avg time, normalized) * 0.20
  ROUND(
    (perf.customer_satisfaction_score / 5.0 * 100) * 0.30
    + perf.first_time_fix_rate_pct * 0.30
    + (100 - perf.reopen_rate_pct) * 0.20
    + (CASE
        WHEN perf.avg_completion_time_mins <= 45 THEN 100
        WHEN perf.avg_completion_time_mins <= 60 THEN 90
        WHEN perf.avg_completion_time_mins <= 90 THEN 75
        WHEN perf.avg_completion_time_mins <= 120 THEN 60
        ELSE 40
       END) * 0.20,
    2
  ) AS tech_score,

  -- Years of experience
  ROUND(DATEDIFF(current_date(), tech.hire_date) / 365.25, 1) AS years_experience

FROM silver_technicians tech
INNER JOIN silver_tech_performance perf
  ON tech.tech_id = perf.tech_id;
