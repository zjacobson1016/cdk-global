"""
Bronze: Ingest pay stub PDFs from Unity Catalog Volume.
Uses ai_parse_document to extract text, then ai_query to structure the
content into employee/income fields for downstream joining on application_id.

Source: /Volumes/{catalog}/{schema}/raw_data/pay_stubs
Filenames: {application_id}_paystub.pdf  (e.g. APP-000001_paystub.pdf)
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

catalog = spark.conf.get("catalog", "main")
schema = spark.conf.get("schema", "lender_approval")
volume_path = f"/Volumes/{catalog}/{schema}/raw_data/pay_stubs"

# Prompt uses doubled single-quotes to safely embed in SQL string literals
EXTRACTION_PROMPT = (
    "Extract the following fields from this pay stub or earnings statement. "
    "Return ONLY a valid JSON object with these exact keys and types: "
    "employee_name (string, full name), "
    "reference_number (string, the reference or application ID e.g. APP-000001), "
    "employer_name (string, company name), "
    "job_title (string), "
    "pay_date (string, YYYY-MM-DD), "
    "pay_period_start (string, YYYY-MM-DD), "
    "pay_period_end (string, YYYY-MM-DD), "
    "gross_pay (number, current period gross pay in dollars), "
    "total_deductions (number, current period total deductions in dollars), "
    "net_pay (number, current period net pay in dollars), "
    "federal_tax (number, current period federal income tax in dollars), "
    "state_tax (number, current period state income tax in dollars), "
    "retirement_contribution (number, current period 401k or retirement in dollars), "
    "ytd_gross (number, year-to-date gross pay in dollars), "
    "ytd_net (number, year-to-date net pay in dollars). "
    "Return ONLY the JSON object, no markdown, no explanation. "
    "Document text: "
)

SCHEMA_DDL = (
    "employee_name STRING, reference_number STRING, employer_name STRING, "
    "job_title STRING, pay_date STRING, pay_period_start STRING, "
    "pay_period_end STRING, gross_pay DOUBLE, total_deductions DOUBLE, "
    "net_pay DOUBLE, federal_tax DOUBLE, state_tax DOUBLE, "
    "retirement_contribution DOUBLE, ytd_gross DOUBLE, ytd_net DOUBLE"
)


@dp.table(name="bronze_pay_stubs", cluster_by=["pay_date"])
def bronze_pay_stubs():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "binaryFile")
        .load(volume_path)
        # Extract application_id from filename: APP-000001_paystub.pdf
        .withColumn(
            "application_id",
            F.regexp_extract(F.col("path"), r"(APP-\d{6})", 1),
        )
        # Step 1: Parse PDF binary into document elements
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
        # Step 3: Use LLM to extract structured fields (returns JSON string)
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
            F.col("extracted.employee_name").alias("employee_name"),
            F.col("extracted.reference_number").alias("reference_number"),
            F.col("extracted.employer_name").alias("employer_name"),
            F.col("extracted.job_title").alias("job_title"),
            F.col("extracted.pay_date").alias("pay_date"),
            F.col("extracted.pay_period_start").alias("pay_period_start"),
            F.col("extracted.pay_period_end").alias("pay_period_end"),
            F.col("extracted.gross_pay").alias("gross_pay"),
            F.col("extracted.total_deductions").alias("total_deductions"),
            F.col("extracted.net_pay").alias("net_pay"),
            F.col("extracted.federal_tax").alias("federal_tax"),
            F.col("extracted.state_tax").alias("state_tax"),
            F.col("extracted.retirement_contribution").alias("retirement_contribution"),
            F.col("extracted.ytd_gross").alias("ytd_gross"),
            F.col("extracted.ytd_net").alias("ytd_net"),
            F.current_timestamp().alias("_ingested_at"),
            F.col("path").alias("_source_file"),
        )
    )
