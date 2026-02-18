"""
Bronze: Ingest photo ID images (JPEG) from Unity Catalog Volume.
Uses ai_parse_document to extract text from driver license images,
then ai_query to structure identity fields for downstream joining.

Source: /Volumes/{catalog}/{schema}/raw_data/photo_ids
Filenames: {application_id}_photoid.jpg  (e.g. APP-000001_photoid.jpg)
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

catalog = spark.conf.get("catalog", "main")
schema = spark.conf.get("schema", "lender_approval")
volume_path = f"/Volumes/{catalog}/{schema}/raw_data/photo_ids"

# Prompt avoids single-quotes so it embeds safely in SQL string literals
EXTRACTION_PROMPT = (
    "Extract the following fields from this driver license or photo ID image. "
    "Return ONLY a valid JSON object with these exact keys and types: "
    "full_name (string, full name as shown on the ID), "
    "date_of_birth (string, YYYY-MM-DD format), "
    "address (string, full street address including city state zip), "
    "license_number (string, driver license or ID number), "
    "state (string, two-letter state abbreviation), "
    "sex (string, M or F), "
    "expiration_date (string, YYYY-MM-DD format), "
    "eye_color (string, e.g. BRN BLU GRN), "
    "height (string, e.g. 5 ft 10 in), "
    "weight (string, e.g. 175 lbs). "
    "Return ONLY the JSON object, no markdown, no explanation. "
    "Document text: "
)

SCHEMA_DDL = (
    "full_name STRING, date_of_birth STRING, address STRING, "
    "license_number STRING, state STRING, sex STRING, "
    "expiration_date STRING, eye_color STRING, height STRING, weight STRING"
)


@dp.table(name="bronze_photo_ids", cluster_by=["state"])
def bronze_photo_ids():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .load(volume_path)
        # Extract application_id from filename: APP-000001_photoid.jpg
        .withColumn(
            "application_id",
            F.regexp_extract(F.col("path"), r"(APP-\d{6})", 1),
        )
        # Step 1: Parse image into document elements
        .withColumn("parsed", F.expr("ai_parse_document(content)"))
        # Step 2: Concatenate all text elements
        .withColumn(
            "full_text",
            F.expr(
                """concat_ws(
                    '\n',
                    transform(
                        try_cast(parsed:document:elements AS ARRAY<VARIANT>),
                        element -> try_cast(element:content AS STRING)
                    )
                )"""
            ),
        )
        # Step 3: Use LLM to extract structured identity fields (returns JSON string)
        .withColumn(
            "extracted_json",
            F.expr(
                f"""ai_query(
                    'databricks-meta-llama-3-3-70b-instruct',
                    concat('{EXTRACTION_PROMPT}', full_text)
                )"""
            ),
        )
        # Step 4: Parse JSON string into typed struct
        .withColumn("extracted", F.from_json(F.col("extracted_json"), SCHEMA_DDL))
        # Step 5: Flatten into columns
        .select(
            F.col("application_id"),
            F.col("extracted.full_name").alias("full_name"),
            F.col("extracted.date_of_birth").alias("date_of_birth"),
            F.col("extracted.address").alias("address"),
            F.col("extracted.license_number").alias("license_number"),
            F.col("extracted.state").alias("state"),
            F.col("extracted.sex").alias("sex"),
            F.col("extracted.expiration_date").alias("expiration_date"),
            F.col("extracted.eye_color").alias("eye_color"),
            F.col("extracted.height").alias("height"),
            F.col("extracted.weight").alias("weight"),
            F.current_timestamp().alias("_ingested_at"),
            F.col("path").alias("_source_file"),
        )
    )
