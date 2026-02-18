"""
Gold: ML-ready feature table with income verification, identity checks,
document completeness flags, and train/test split.
Downstream training and batch inference read from this table.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F


@dp.table(name="gold_lender_features", cluster_by=["application_date"])
def gold_lender_features():
    return (
        spark.read.table("silver_applications")
        # --- Income verification features ---
        .withColumn(
            "verified_annual_income",
            F.round(F.col("verified_period_income") * 26, 2),  # biweekly → annual
        )
        .withColumn(
            "income_verification_ratio",
            F.when(
                (F.col("income") > 0) & F.col("verified_annual_income").isNotNull(),
                F.round(F.col("verified_annual_income") / F.col("income"), 4),
            ),
        )
        # --- Identity verification features ---
        .withColumn(
            "name_match",
            F.when(
                F.col("verified_employee_name").isNotNull() & F.col("id_full_name").isNotNull(),
                F.when(
                    F.upper(F.trim(F.col("verified_employee_name")))
                    == F.upper(F.trim(F.col("id_full_name"))),
                    1,
                ).otherwise(0),
            ).otherwise(F.lit(None).cast("int")),
        )
        .withColumn(
            "id_expired",
            F.when(
                F.col("id_expiration_date").isNotNull(),
                F.when(F.col("id_expiration_date") < F.current_date(), 1).otherwise(0),
            ).otherwise(F.lit(None).cast("int")),
        )
        # --- Document completeness flags ---
        .withColumn(
            "has_pay_stub",
            F.when(F.col("verified_employer").isNotNull(), 1).otherwise(0),
        )
        .withColumn(
            "has_photo_id",
            F.when(F.col("id_license_number").isNotNull(), 1).otherwise(0),
        )
        .withColumn(
            "doc_completeness",
            F.col("has_pay_stub") + F.col("has_photo_id"),  # 0, 1, or 2
        )
        # --- Standard ML columns ---
        .withColumn("transaction_ts", F.current_timestamp())
        .withColumn(
            "split",
            F.when(F.rand(42) < 0.8, F.lit("train")).otherwise(F.lit("test")),
        )
        .dropDuplicates(["application_id", "transaction_ts"])
    )
