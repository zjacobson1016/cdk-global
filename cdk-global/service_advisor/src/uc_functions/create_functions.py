"""Register Unity Catalog functions for the Service Advisor Agent.

5 SQL functions that query gold-layer materialized views:
  1. get_todays_appointments   — today's appointments with full customer profiles
  2. get_customer_profile      — detailed profile for a single customer
  3. get_highest_clv_customer  — top CLV customer from today's appointments
  4. get_best_technician       — best-ranked tech for a given service type
  5. get_technician_schedule   — all technicians with current assignment counts
"""
from databricks.connect import DatabricksSession

CATALOG = "mfg_mc_se_sa"
SCHEMA = "cdk_service"

spark = DatabricksSession.builder.profile("group-demo").serverless().getOrCreate()


# ── Tool 1: Get today's appointments with customer profiles ──────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_todays_appointments()
RETURNS TABLE(
  appointment_id STRING,
  appointment_time STRING,
  service_type STRING,
  estimated_duration_mins INT,
  appointment_status STRING,
  advisor_notes STRING,
  customer_id STRING,
  customer_name STRING,
  customer_phone STRING,
  loyalty_tier STRING,
  vehicle_description STRING,
  mileage INT,
  clv_score DECIMAL(8,2),
  clv_tier STRING,
  total_spend DECIMAL(12,2)
)
LANGUAGE SQL
COMMENT 'Get the 5 most recent appointments with full customer profile, vehicle info, and CLV score. Use this when the advisor asks about upcoming schedule or daily briefing.'
RETURN
  SELECT
    appointment_id,
    appointment_time,
    service_type,
    estimated_duration_mins,
    appointment_status,
    advisor_notes,
    customer_id,
    customer_name,
    customer_phone,
    loyalty_tier,
    vehicle_description,
    mileage,
    clv_score,
    clv_tier,
    total_spend
  FROM {CATALOG}.{SCHEMA}.gold_daily_appointment_profiles
  WHERE appointment_status IN ('Scheduled', 'Checked-In', 'In-Progress')
  ORDER BY appointment_date DESC, appointment_time DESC
  LIMIT 5
""")
print("1/5 get_todays_appointments")


# ── Tool 2: Get customer profile ─────────────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_customer_profile(customer_id_input STRING)
RETURNS TABLE(
  customer_id STRING,
  customer_name STRING,
  customer_phone STRING,
  customer_email STRING,
  preferred_contact STRING,
  loyalty_tier STRING,
  customer_since DATE,
  vehicle_description STRING,
  vin STRING,
  mileage INT,
  last_service_date DATE,
  total_spend DECIMAL(12,2),
  visit_count INT,
  avg_repair_order_value DECIMAL(10,2),
  months_as_customer INT,
  referral_count INT,
  clv_score DECIMAL(8,2),
  clv_tier STRING
)
LANGUAGE SQL
COMMENT 'Get full customer profile including contact info, vehicle details, and lifetime value metrics. Use when the advisor asks about a specific customer.'
RETURN
  SELECT DISTINCT
    customer_id,
    customer_name,
    customer_phone,
    customer_email,
    preferred_contact,
    loyalty_tier,
    customer_since,
    vehicle_description,
    vin,
    mileage,
    last_service_date,
    total_spend,
    visit_count,
    avg_repair_order_value,
    months_as_customer,
    referral_count,
    clv_score,
    clv_tier
  FROM {CATALOG}.{SCHEMA}.gold_daily_appointment_profiles
  WHERE customer_id = customer_id_input
  LIMIT 5
""")
print("2/5 get_customer_profile")


# ── Tool 3: Get highest CLV customer from today's appointments ───────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_highest_clv_customer()
RETURNS TABLE(
  appointment_id STRING,
  appointment_time STRING,
  service_type STRING,
  customer_id STRING,
  customer_name STRING,
  customer_phone STRING,
  loyalty_tier STRING,
  vehicle_description STRING,
  clv_score DECIMAL(8,2),
  clv_tier STRING,
  total_spend DECIMAL(12,2),
  visit_count INT,
  referral_count INT
)
LANGUAGE SQL
COMMENT 'Identify the highest lifetime value customer from the latest appointments. Use when the advisor asks who their top customer is or which customer deserves VIP treatment.'
RETURN
  SELECT
    appointment_id,
    appointment_time,
    service_type,
    customer_id,
    customer_name,
    customer_phone,
    loyalty_tier,
    vehicle_description,
    clv_score,
    clv_tier,
    total_spend,
    visit_count,
    referral_count
  FROM {CATALOG}.{SCHEMA}.gold_daily_appointment_profiles
  WHERE appointment_status IN ('Scheduled', 'Checked-In', 'In-Progress')
    AND appointment_date = (
      SELECT MAX(appointment_date)
      FROM {CATALOG}.{SCHEMA}.gold_daily_appointment_profiles
      WHERE appointment_status IN ('Scheduled', 'Checked-In', 'In-Progress')
    )
  ORDER BY clv_score DESC
  LIMIT 1
""")
print("3/5 get_highest_clv_customer")


# ── Tool 4: Get best technician for a service type ───────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_best_technician(service_type_input STRING)
RETURNS TABLE(
  tech_id STRING,
  technician_name STRING,
  specialization STRING,
  certifications STRING,
  shift STRING,
  tech_score DOUBLE,
  customer_satisfaction_score DECIMAL(3,2),
  first_time_fix_rate_pct DECIMAL(5,1),
  reopen_rate_pct DECIMAL(5,1),
  avg_completion_time_mins DECIMAL(6,1),
  years_experience DOUBLE
)
LANGUAGE SQL
COMMENT 'Find the best-ranked technician for a given service type based on specialization match and composite performance score. Use when assigning a tech to a customer\\'s vehicle repair.'
RETURN
  SELECT
    tech_id,
    technician_name,
    specialization,
    certifications,
    shift,
    tech_score,
    customer_satisfaction_score,
    first_time_fix_rate_pct,
    reopen_rate_pct,
    avg_completion_time_mins,
    years_experience
  FROM {CATALOG}.{SCHEMA}.gold_technician_rankings
  WHERE
    CASE service_type_input
      WHEN 'Oil Change' THEN specialization IN ('General Service', 'Engine & Drivetrain')
      WHEN 'Brake Service' THEN specialization IN ('Brakes & Suspension', 'General Service')
      WHEN 'Transmission Service' THEN specialization IN ('Transmission', 'Engine & Drivetrain')
      WHEN 'Engine Diagnostics' THEN specialization IN ('Engine & Drivetrain', 'General Service')
      WHEN 'Tire Rotation' THEN specialization IN ('General Service', 'Brakes & Suspension')
      WHEN 'A/C Service' THEN specialization IN ('Electrical & HVAC', 'General Service')
      WHEN 'Recall Service' THEN specialization IN ('General Service', 'Engine & Drivetrain')
      WHEN 'Multi-Point Inspection' THEN specialization IN ('General Service', 'Engine & Drivetrain')
      WHEN 'Suspension Repair' THEN specialization IN ('Brakes & Suspension', 'General Service')
      WHEN 'Electrical Diagnostics' THEN specialization IN ('Electrical & HVAC', 'General Service')
      WHEN 'Coolant Flush' THEN specialization IN ('Engine & Drivetrain', 'General Service')
      WHEN 'Battery Replacement' THEN specialization IN ('Electrical & HVAC', 'General Service')
      ELSE TRUE
    END
  ORDER BY tech_score DESC
  LIMIT 3
""")
print("4/5 get_best_technician")


# ── Tool 5: Get technician schedule / availability ───────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_technician_schedule()
RETURNS TABLE(
  tech_id STRING,
  technician_name STRING,
  specialization STRING,
  shift STRING,
  tech_score DOUBLE,
  current_assignments BIGINT
)
LANGUAGE SQL
COMMENT 'Show all technicians with their current assignment count from the latest assignment date. Use when checking technician availability or workload balance.'
RETURN
  SELECT
    tr.tech_id,
    tr.technician_name,
    tr.specialization,
    tr.shift,
    tr.tech_score,
    COALESCE(asgn.assignment_count, 0) AS current_assignments
  FROM {CATALOG}.{SCHEMA}.gold_technician_rankings tr
  LEFT JOIN (
    SELECT
      tech_id,
      COUNT(*) AS assignment_count
    FROM cdk_service_agent.public.technician_assignments
    WHERE LOWER(status) = 'assigned'
    GROUP BY tech_id
  ) asgn ON tr.tech_id = asgn.tech_id
  ORDER BY tr.tech_score DESC
""")
print("5/5 get_technician_schedule")


print(f"\nAll 5 UC functions created in {CATALOG}.{SCHEMA}")
