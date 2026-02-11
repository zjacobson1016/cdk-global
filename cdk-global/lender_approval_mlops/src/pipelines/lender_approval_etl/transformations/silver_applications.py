"""
Silver: Clean and validate loan applications. Cast types, drop nulls, valid ranges.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(name="silver_applications", cluster_by=["application_date"])
def silver_applications():
    return (
        spark.read.table("bronze_applications")
        .filter(F.col("application_id").isNotNull())
        .withColumn("application_date", F.to_date(F.col("application_date")))
        .withColumn("income", F.col("income").cast("double"))
        .withColumn("credit_score", F.col("credit_score").cast("int"))
        .withColumn("employment_years", F.col("employment_years").cast("double"))
        .withColumn("debt_to_income", F.col("debt_to_income").cast("double"))
        .withColumn("loan_amount", F.col("loan_amount").cast("double"))
        .withColumn("approved", F.col("approved").cast("int"))
        .filter(
            (F.col("credit_score") >= 300) & (F.col("credit_score") <= 850)
            & (F.col("income") > 0)
            & (F.col("debt_to_income") > 0) & (F.col("debt_to_income") <= 1)
            & (F.col("loan_amount") > 0)
        )
    )
