# Databricks notebook source
# MAGIC %md
# MAGIC # Generate lender programs reference data
# MAGIC Creates a `lender_programs` table with realistic auto-lending programs
# MAGIC from multiple lenders. Used by the `shop_lenders` UC function to compare
# MAGIC lender offers for a given borrower profile.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType, BooleanType,
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Define lender programs
# MAGIC Each row is a lending program offered by a specific lender. Dealers use
# MAGIC these to "shop" across lenders for the best rate/terms for their customer.

# COMMAND ----------

lender_programs = [
    # ── Capital One Auto Finance ──
    {"lender_id": "L001", "lender_name": "Capital One Auto Finance", "program_name": "Prime New Vehicle",
     "min_credit_score": 700, "min_income": 35000, "apr": 4.49, "max_apr": 6.99,
     "min_loan_amount": 10000, "max_loan_amount": 75000,
     "min_term_months": 24, "max_term_months": 72,
     "max_ltv": 120.0, "min_vehicle_year": 2023, "is_active": True},
    {"lender_id": "L001", "lender_name": "Capital One Auto Finance", "program_name": "Prime Used Vehicle",
     "min_credit_score": 680, "min_income": 30000, "apr": 5.49, "max_apr": 8.49,
     "min_loan_amount": 8000, "max_loan_amount": 60000,
     "min_term_months": 24, "max_term_months": 72,
     "max_ltv": 110.0, "min_vehicle_year": 2019, "is_active": True},
    {"lender_id": "L001", "lender_name": "Capital One Auto Finance", "program_name": "Near Prime",
     "min_credit_score": 600, "min_income": 25000, "apr": 8.99, "max_apr": 14.99,
     "min_loan_amount": 5000, "max_loan_amount": 45000,
     "min_term_months": 24, "max_term_months": 60,
     "max_ltv": 100.0, "min_vehicle_year": 2018, "is_active": True},

    # ── Ally Financial ──
    {"lender_id": "L002", "lender_name": "Ally Financial", "program_name": "SmartAuto New",
     "min_credit_score": 680, "min_income": 30000, "apr": 3.99, "max_apr": 6.49,
     "min_loan_amount": 10000, "max_loan_amount": 100000,
     "min_term_months": 24, "max_term_months": 84,
     "max_ltv": 130.0, "min_vehicle_year": 2024, "is_active": True},
    {"lender_id": "L002", "lender_name": "Ally Financial", "program_name": "SmartAuto Used",
     "min_credit_score": 650, "min_income": 28000, "apr": 5.29, "max_apr": 9.99,
     "min_loan_amount": 7500, "max_loan_amount": 75000,
     "min_term_months": 24, "max_term_months": 72,
     "max_ltv": 115.0, "min_vehicle_year": 2018, "is_active": True},
    {"lender_id": "L002", "lender_name": "Ally Financial", "program_name": "Subprime Recovery",
     "min_credit_score": 520, "min_income": 22000, "apr": 12.99, "max_apr": 21.99,
     "min_loan_amount": 5000, "max_loan_amount": 30000,
     "min_term_months": 24, "max_term_months": 60,
     "max_ltv": 90.0, "min_vehicle_year": 2017, "is_active": True},

    # ── Chase Auto ──
    {"lender_id": "L003", "lender_name": "Chase Auto", "program_name": "Preferred New",
     "min_credit_score": 720, "min_income": 40000, "apr": 3.49, "max_apr": 5.49,
     "min_loan_amount": 15000, "max_loan_amount": 100000,
     "min_term_months": 36, "max_term_months": 72,
     "max_ltv": 125.0, "min_vehicle_year": 2024, "is_active": True},
    {"lender_id": "L003", "lender_name": "Chase Auto", "program_name": "Standard Used",
     "min_credit_score": 660, "min_income": 32000, "apr": 5.99, "max_apr": 9.49,
     "min_loan_amount": 10000, "max_loan_amount": 65000,
     "min_term_months": 24, "max_term_months": 60,
     "max_ltv": 105.0, "min_vehicle_year": 2019, "is_active": True},

    # ── TD Auto Finance ──
    {"lender_id": "L004", "lender_name": "TD Auto Finance", "program_name": "Tier 1 New",
     "min_credit_score": 740, "min_income": 45000, "apr": 2.99, "max_apr": 4.99,
     "min_loan_amount": 20000, "max_loan_amount": 90000,
     "min_term_months": 36, "max_term_months": 72,
     "max_ltv": 130.0, "min_vehicle_year": 2024, "is_active": True},
    {"lender_id": "L004", "lender_name": "TD Auto Finance", "program_name": "Tier 2 Certified Pre-Owned",
     "min_credit_score": 680, "min_income": 35000, "apr": 4.49, "max_apr": 7.49,
     "min_loan_amount": 12000, "max_loan_amount": 70000,
     "min_term_months": 24, "max_term_months": 72,
     "max_ltv": 115.0, "min_vehicle_year": 2021, "is_active": True},

    # ── Wells Fargo Dealer Services ──
    {"lender_id": "L005", "lender_name": "Wells Fargo Dealer Services", "program_name": "Prime Auto",
     "min_credit_score": 700, "min_income": 35000, "apr": 4.29, "max_apr": 6.79,
     "min_loan_amount": 10000, "max_loan_amount": 80000,
     "min_term_months": 24, "max_term_months": 72,
     "max_ltv": 120.0, "min_vehicle_year": 2022, "is_active": True},
    {"lender_id": "L005", "lender_name": "Wells Fargo Dealer Services", "program_name": "Non-Prime",
     "min_credit_score": 580, "min_income": 24000, "apr": 10.49, "max_apr": 17.99,
     "min_loan_amount": 5000, "max_loan_amount": 35000,
     "min_term_months": 24, "max_term_months": 60,
     "max_ltv": 95.0, "min_vehicle_year": 2018, "is_active": True},

    # ── Westlake Financial Services ──
    {"lender_id": "L006", "lender_name": "Westlake Financial Services", "program_name": "Deep Subprime",
     "min_credit_score": 450, "min_income": 18000, "apr": 16.99, "max_apr": 24.99,
     "min_loan_amount": 3000, "max_loan_amount": 25000,
     "min_term_months": 24, "max_term_months": 48,
     "max_ltv": 85.0, "min_vehicle_year": 2015, "is_active": True},
    {"lender_id": "L006", "lender_name": "Westlake Financial Services", "program_name": "Second Chance",
     "min_credit_score": 500, "min_income": 20000, "apr": 14.49, "max_apr": 21.99,
     "min_loan_amount": 4000, "max_loan_amount": 30000,
     "min_term_months": 24, "max_term_months": 60,
     "max_ltv": 90.0, "min_vehicle_year": 2016, "is_active": True},

    # ── Navy Federal Credit Union ──
    {"lender_id": "L007", "lender_name": "Navy Federal Credit Union", "program_name": "New Auto Loan",
     "min_credit_score": 670, "min_income": 28000, "apr": 3.79, "max_apr": 6.29,
     "min_loan_amount": 10000, "max_loan_amount": 80000,
     "min_term_months": 36, "max_term_months": 84,
     "max_ltv": 125.0, "min_vehicle_year": 2024, "is_active": True},
    {"lender_id": "L007", "lender_name": "Navy Federal Credit Union", "program_name": "Used Auto Loan",
     "min_credit_score": 640, "min_income": 25000, "apr": 4.99, "max_apr": 8.99,
     "min_loan_amount": 5000, "max_loan_amount": 60000,
     "min_term_months": 24, "max_term_months": 72,
     "max_ltv": 110.0, "min_vehicle_year": 2017, "is_active": True},

    # ── AmeriCredit (GM Financial) ──
    {"lender_id": "L008", "lender_name": "AmeriCredit (GM Financial)", "program_name": "GM Loyalty New",
     "min_credit_score": 620, "min_income": 26000, "apr": 4.99, "max_apr": 9.99,
     "min_loan_amount": 12000, "max_loan_amount": 80000,
     "min_term_months": 36, "max_term_months": 84,
     "max_ltv": 130.0, "min_vehicle_year": 2024, "is_active": True},
    {"lender_id": "L008", "lender_name": "AmeriCredit (GM Financial)", "program_name": "Standard Used",
     "min_credit_score": 550, "min_income": 22000, "apr": 9.49, "max_apr": 17.49,
     "min_loan_amount": 5000, "max_loan_amount": 45000,
     "min_term_months": 24, "max_term_months": 60,
     "max_ltv": 100.0, "min_vehicle_year": 2018, "is_active": True},
]

# COMMAND ----------

schema_def = StructType([
    StructField("lender_id", StringType()),
    StructField("lender_name", StringType()),
    StructField("program_name", StringType()),
    StructField("min_credit_score", IntegerType()),
    StructField("min_income", DoubleType()),
    StructField("apr", DoubleType()),
    StructField("max_apr", DoubleType()),
    StructField("min_loan_amount", DoubleType()),
    StructField("max_loan_amount", DoubleType()),
    StructField("min_term_months", IntegerType()),
    StructField("max_term_months", IntegerType()),
    StructField("max_ltv", DoubleType()),
    StructField("min_vehicle_year", IntegerType()),
    StructField("is_active", BooleanType()),
])

programs_df = spark.createDataFrame(lender_programs, schema=schema_def)

programs_df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(
    f"{catalog}.{schema}.lender_programs"
)

print(f"Created {catalog}.{schema}.lender_programs with {programs_df.count()} programs from {programs_df.select('lender_name').distinct().count()} lenders")
display(programs_df.orderBy("apr"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create `shop_lenders` UC function
# MAGIC This SQL function takes a borrower profile and returns matching lender
# MAGIC programs sorted by APR.  The Lender Shopping Agent calls this as a
# MAGIC UC Function tool to provide rate comparisons in natural language.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE FUNCTION {catalog}.{schema}.shop_lenders(
  credit_score_in INT,
  annual_income_in DOUBLE,
  loan_amount_in DOUBLE,
  loan_term_months_in INT,
  vehicle_year_in INT
)
RETURNS TABLE(
  lender_name STRING,
  program_name STRING,
  apr DOUBLE,
  max_apr DOUBLE,
  estimated_monthly_payment DOUBLE,
  max_ltv DOUBLE,
  approval_likelihood STRING
)
LANGUAGE SQL
COMMENT 'Shop available auto lenders for a given borrower profile. Returns matching programs sorted by best APR with estimated monthly payment and approval likelihood.'
RETURN
  SELECT
    lender_name,
    program_name,
    apr,
    max_apr,
    ROUND(
      loan_amount_in * (apr / 1200.0)
        * POWER(1 + apr / 1200.0, loan_term_months_in)
        / (POWER(1 + apr / 1200.0, loan_term_months_in) - 1),
      2
    ) AS estimated_monthly_payment,
    max_ltv,
    CASE
      WHEN credit_score_in >= min_credit_score + 60
       AND annual_income_in >= min_income * 1.3
       THEN 'HIGH'
      WHEN credit_score_in >= min_credit_score + 20
       AND annual_income_in >= min_income
       THEN 'MEDIUM'
      ELSE 'LOW'
    END AS approval_likelihood
  FROM {catalog}.{schema}.lender_programs
  WHERE is_active = true
    AND credit_score_in >= min_credit_score
    AND loan_amount_in BETWEEN min_loan_amount AND max_loan_amount
    AND loan_term_months_in BETWEEN min_term_months AND max_term_months
    AND vehicle_year_in >= min_vehicle_year
  ORDER BY apr ASC
""")

print(f"Created UC function: {catalog}.{schema}.shop_lenders")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke test

# COMMAND ----------

results = spark.sql(f"""
  SELECT * FROM {catalog}.{schema}.shop_lenders(
    credit_score_in => 720,
    annual_income_in => 65000,
    loan_amount_in => 35000,
    loan_term_months_in => 60,
    vehicle_year_in => 2024
  )
""")
print(f"Found {results.count()} matching programs for a 720-credit / $65K income / $35K loan:")
display(results)

# COMMAND ----------

# Low credit test
results_low = spark.sql(f"""
  SELECT * FROM {catalog}.{schema}.shop_lenders(
    credit_score_in => 540,
    annual_income_in => 28000,
    loan_amount_in => 15000,
    loan_term_months_in => 48,
    vehicle_year_in => 2020
  )
""")
print(f"Found {results_low.count()} matching programs for a 540-credit / $28K income / $15K loan:")
display(results_low)
