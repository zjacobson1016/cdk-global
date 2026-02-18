# Databricks notebook source
# MAGIC %md
# MAGIC # Create Lending Analytics Metric View
# MAGIC Creates a governed metric view on `gold_lender_features` that provides
# MAGIC standardized KPIs for the auto-lending pipeline: approval rates, loan
# MAGIC volumes, borrower profiles, credit tiers, and document verification rates.
# MAGIC
# MAGIC The metric view enables conversational analytics via Genie and dashboards
# MAGIC by pre-defining dimensions and measures that any user can query with
# MAGIC `MEASURE()` syntax.

# COMMAND ----------

dbutils.widgets.text("catalog", "mfg_mc_se_sa", "Catalog")
dbutils.widgets.text("schema", "cdk", "Schema")

# COMMAND ----------

# MAGIC %run ./_setup_lender

# COMMAND ----------

# MAGIC %md
# MAGIC ## Define the metric view
# MAGIC Source: `gold_lender_features` (15K applications with ML features,
# MAGIC income verification, identity checks, and document completeness flags).

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {catalog}.{schema}.lending_analytics_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: "1.1"
source: {catalog}.{schema}.gold_lender_features
comment: "CDK Global lending analytics — application pipeline, approval rates, borrower profiles, document verification, and lender program coverage"

dimensions:
  - name: "Application Month"
    expr: "DATE_TRUNC('MONTH', application_date)"
    comment: "Month the application was submitted"
  - name: "Application Week"
    expr: "DATE_TRUNC('WEEK', application_date)"
    comment: "Week the application was submitted"
  - name: "Loan Purpose"
    expr: "loan_purpose"
    comment: "Purpose of the auto loan"
  - name: "Approval Status"
    expr: "CASE WHEN approved = 1 THEN 'Approved' ELSE 'Denied' END"
    comment: "Whether the application was approved or denied"
  - name: "Credit Tier"
    expr: "CASE WHEN credit_score >= 740 THEN 'Super Prime (740+)' WHEN credit_score >= 700 THEN 'Prime (700-739)' WHEN credit_score >= 660 THEN 'Near Prime (660-699)' WHEN credit_score >= 600 THEN 'Subprime (600-659)' ELSE 'Deep Subprime (<600)' END"
    comment: "Credit score tier classification"
  - name: "Doc Completeness Level"
    expr: "CASE WHEN doc_completeness = 2 THEN 'Full (Pay Stub + ID)' WHEN doc_completeness = 1 THEN 'Partial' ELSE 'None' END"
    comment: "Document verification completeness"
  - name: "Has Pay Stub"
    expr: "CASE WHEN has_pay_stub = 1 THEN 'Yes' ELSE 'No' END"
    comment: "Whether a pay stub was submitted"
  - name: "Has Photo ID"
    expr: "CASE WHEN has_photo_id = 1 THEN 'Yes' ELSE 'No' END"
    comment: "Whether a photo ID was submitted"
  - name: "DTI Bucket"
    expr: "CASE WHEN debt_to_income < 0.20 THEN 'Low (<20%)' WHEN debt_to_income < 0.35 THEN 'Moderate (20-35%)' WHEN debt_to_income < 0.45 THEN 'High (35-45%)' ELSE 'Very High (45%+)' END"
    comment: "Debt-to-income ratio bucket"
  - name: "Loan Amount Band"
    expr: "CASE WHEN loan_amount < 10000 THEN 'Under $10K' WHEN loan_amount < 25000 THEN '$10K-$25K' WHEN loan_amount < 50000 THEN '$25K-$50K' ELSE '$50K+' END"
    comment: "Loan amount range"
  - name: "Applicant State"
    expr: "COALESCE(id_state, 'Unknown')"
    comment: "State from photo ID"
  - name: "Employment Tenure"
    expr: "CASE WHEN employment_years < 1 THEN 'Under 1 Year' WHEN employment_years < 3 THEN '1-3 Years' WHEN employment_years < 7 THEN '3-7 Years' ELSE '7+ Years' END"
    comment: "Employment tenure bucket"

measures:
  - name: "Total Applications"
    expr: "COUNT(*)"
    comment: "Total number of loan applications"
  - name: "Approved Applications"
    expr: "SUM(approved)"
    comment: "Number of approved applications"
  - name: "Denied Applications"
    expr: "SUM(CASE WHEN approved = 0 THEN 1 ELSE 0 END)"
    comment: "Number of denied applications"
  - name: "Approval Rate"
    expr: "ROUND(AVG(CAST(approved AS DOUBLE)), 4)"
    comment: "Fraction of applications approved (0-1)"
  - name: "Total Loan Volume"
    expr: "SUM(loan_amount)"
    comment: "Sum of all requested loan amounts"
  - name: "Avg Loan Amount"
    expr: "ROUND(AVG(loan_amount), 2)"
    comment: "Average requested loan amount"
  - name: "Avg Credit Score"
    expr: "ROUND(AVG(CAST(credit_score AS DOUBLE)), 0)"
    comment: "Average applicant credit score"
  - name: "Avg Income"
    expr: "ROUND(AVG(income), 2)"
    comment: "Average applicant stated income"
  - name: "Avg Debt-to-Income"
    expr: "ROUND(AVG(debt_to_income), 4)"
    comment: "Average debt-to-income ratio"
  - name: "Avg Employment Years"
    expr: "ROUND(AVG(employment_years), 1)"
    comment: "Average years of employment"
  - name: "Pay Stub Submission Rate"
    expr: "ROUND(AVG(CAST(has_pay_stub AS DOUBLE)), 4)"
    comment: "Fraction of applications with pay stub"
  - name: "Photo ID Submission Rate"
    expr: "ROUND(AVG(CAST(has_photo_id AS DOUBLE)), 4)"
    comment: "Fraction of applications with photo ID"
  - name: "Full Doc Rate"
    expr: "ROUND(AVG(CASE WHEN doc_completeness = 2 THEN 1.0 ELSE 0.0 END), 4)"
    comment: "Fraction of applications with both pay stub and photo ID"
  - name: "Median Loan Amount"
    expr: "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY loan_amount)"
    comment: "Median requested loan amount"
  - name: "Median Credit Score"
    expr: "PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY CAST(credit_score AS DOUBLE))"
    comment: "Median credit score"
  - name: "Approved Loan Volume"
    expr: "SUM(CASE WHEN approved = 1 THEN loan_amount ELSE 0 END)"
    comment: "Total loan volume for approved applications"
  - name: "Avg Approved Loan Amount"
    expr: "ROUND(AVG(CASE WHEN approved = 1 THEN loan_amount END), 2)"
    comment: "Average loan amount among approved applications"
$$
""")

print(f"Created metric view: {catalog}.{schema}.lending_analytics_metrics")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Smoke test — query the metric view

# COMMAND ----------

result = spark.sql(f"""
SELECT `Credit Tier`, `Approval Status`,
       MEASURE(`Total Applications`),
       MEASURE(`Approval Rate`),
       MEASURE(`Avg Credit Score`),
       MEASURE(`Avg Loan Amount`)
FROM {catalog}.{schema}.lending_analytics_metrics
GROUP BY `Credit Tier`, `Approval Status`
ORDER BY `Credit Tier`
""")
display(result)

# COMMAND ----------

result2 = spark.sql(f"""
SELECT `Loan Purpose`,
       MEASURE(`Total Applications`),
       MEASURE(`Approval Rate`),
       MEASURE(`Total Loan Volume`),
       MEASURE(`Avg Debt-to-Income`)
FROM {catalog}.{schema}.lending_analytics_metrics
GROUP BY `Loan Purpose`
ORDER BY MEASURE(`Total Applications`) DESC
""")
display(result2)
