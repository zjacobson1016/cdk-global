"""
Gold: ML-ready feature table with train/test split and scoring timestamp.
Downstream training and batch inference read from this table.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

@dp.table(name="gold_lender_features", cluster_by=["application_date"])
def gold_lender_features():
    return (
        spark.read.table("silver_applications")
        .withColumn("transaction_ts", F.current_timestamp())
        .withColumn(
            "split",
            F.when(F.rand(42) < 0.8, F.lit("train")).otherwise(F.lit("test"))
        )
    )
