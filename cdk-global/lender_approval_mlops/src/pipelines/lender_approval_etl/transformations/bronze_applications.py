"""
Bronze: Ingest structured loan applications from parquet files via Auto Loader.
Source: /Volumes/{catalog}/{schema}/raw_data/applications  (from 01_generate_lender_data.py)

Pipeline configuration (set in bundle pipeline yml):
  - catalog: Unity Catalog name
  - schema: Schema name
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

catalog = spark.conf.get("catalog", "main")
schema = spark.conf.get("schema", "lender_approval")
volume_path = f"/Volumes/{catalog}/{schema}/raw_data/applications"
base_path = f"/Volumes/{catalog}/{schema}/raw_data"


@dp.table(name="bronze_applications", cluster_by=["application_date"])
def bronze_applications():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation", f"{base_path}/applications/_schema")
        .load(volume_path)
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.col("_metadata.file_path"))
    )
