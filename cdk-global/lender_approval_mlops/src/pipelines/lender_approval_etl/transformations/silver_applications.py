"""
Silver: Join structured applications with pay-stub and photo-ID extractions.
All three bronze sources are linked on application_id (primary key).
Left joins ensure applications are retained even if supporting docs are missing.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(name="silver_applications", cluster_by=["application_date"])
def silver_applications():
    # --- Structured applications (parquet) ---
    apps = (
        spark.read.table("bronze_applications")
        .filter(F.col("application_id").isNotNull())
        .withColumn("application_date", F.to_date(F.col("application_date")))
        .withColumn("income", F.col("income").cast("double"))
        .withColumn("credit_score", F.col("credit_score").cast("int"))
        .withColumn("employment_years", F.col("employment_years").cast("double"))
        .withColumn("debt_to_income", F.col("debt_to_income").cast("double"))
        .withColumn("loan_amount", F.col("loan_amount").cast("double"))
        .filter(
            (F.col("credit_score") >= 300) & (F.col("credit_score") <= 850)
            & (F.col("income") > 0)
            & (F.col("debt_to_income") > 0) & (F.col("debt_to_income") <= 1)
            & (F.col("loan_amount") > 0)
        )
        .select(
            "application_id",
            "application_date",
            "income",
            "credit_score",
            "employment_years",
            "debt_to_income",
            "loan_amount",
            "loan_purpose",
            "approved",
        )
    )

    # --- Pay stub extractions ---
    pay_stubs = (
        spark.read.table("bronze_pay_stubs")
        .filter(F.col("application_id").isNotNull() & (F.col("application_id") != ""))
        .select(
            F.col("application_id"),
            F.col("employer_name").alias("verified_employer"),
            F.col("employee_name").alias("verified_employee_name"),
            F.col("job_title").alias("verified_job_title"),
            F.col("gross_pay").alias("verified_period_income"),
            F.col("net_pay").alias("verified_period_net"),
            F.col("ytd_gross").alias("verified_ytd_gross"),
            F.col("ytd_net").alias("verified_ytd_net"),
            F.col("pay_date").alias("pay_stub_date"),
        )
    )

    # --- Photo ID extractions ---
    photo_ids = (
        spark.read.table("bronze_photo_ids")
        .filter(F.col("application_id").isNotNull() & (F.col("application_id") != ""))
        .select(
            F.col("application_id"),
            F.col("full_name").alias("id_full_name"),
            F.to_date(F.col("date_of_birth")).alias("id_date_of_birth"),
            F.col("address").alias("id_address"),
            F.col("license_number").alias("id_license_number"),
            F.col("state").alias("id_state"),
            F.col("sex").alias("id_sex"),
            F.to_date(F.col("expiration_date")).alias("id_expiration_date"),
        )
    )

    # --- Left join all three on application_id ---
    return (
        apps
        .join(pay_stubs, on="application_id", how="left")
        .join(photo_ids, on="application_id", how="left")
    )
