"""
Bronze: Ingest loan applications from Unity Catalog Volume (parquet).
Path is built from pipeline configuration: catalog, schema.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

# Pipeline configuration (set in bundle pipeline yml)
catalog = spark.conf.get("catalog", "main")
schema = spark.conf.get("schema", "lender_approval")
volume_path = f"/Volumes/{catalog}/{schema}/raw_data/applications"


@dp.table(name="bronze_applications", cluster_by=["application_date"])
def bronze_applications():
    return (
        spark.read.format("parquet")
        .load(volume_path)
        .withColumn("_ingested_at", F.current_timestamp())
    )
