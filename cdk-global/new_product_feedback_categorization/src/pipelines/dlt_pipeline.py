# Databricks notebook source
# COMMAND ----------

from pyspark import pipelines as dp
from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration
# MAGIC 
# MAGIC The catalog and schema are automatically configured via the pipeline configuration.
# MAGIC Volume paths are configured for Auto Loader ingestion of Qualtrics survey responses.

# COMMAND ----------

# Get pipeline configuration from Databricks widgets/job parameters
catalog_name = "mfg_mc_se_sa"
schema_name = "cdk"
volume_name = "survey_responses"

# Source path for Qualtrics survey responses
VOLUME_BASE_PATH = f"/Volumes/{catalog_name}/{schema_name}/{volume_name}"
QUALTRICS_RESPONSES_SOURCE_PATH = f"{VOLUME_BASE_PATH}/qualtrics/"

print(f"Pipeline catalog: {catalog_name}")
print(f"Pipeline schema: {schema_name}")
print(f"Qualtrics source path: {QUALTRICS_RESPONSES_SOURCE_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze Layer - Qualtrics Survey Responses
# MAGIC 
# MAGIC Ingests raw Qualtrics new product survey customer responses using Auto Loader.
# MAGIC The full JSON payload is stored as a VARIANT column for flexible downstream processing.

# COMMAND ----------

@dp.table(
    name="bronze_qualtrics_survey_responses",
    comment="Raw Qualtrics new product survey customer responses ingested from JSON files via Auto Loader. Full JSON payload stored as VARIANT.",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true",
        "delta.feature.variantType-preview" : "supported"
    }
)
def bronze_qualtrics_survey_responses():
    """
    Read Qualtrics survey response JSON files from the Unity Catalog volume.
    Stores the complete JSON payload as VARIANT type for flexible downstream processing.
    
    Schema based on qualtrics_customer_response_schema.json:
    - meta: API request metadata
    - result: Survey response data including:
      - responseId, surveyId, responseStatus
      - timestamps (startDate, endDate, recordedDate, durationSeconds)
      - respondent (recipientId, email, firstName, lastName, etc.)
      - locationData (city, state, country, postalCode)
      - embeddedData (customerSegment, productInterest, accountId, etc.)
      - answers (productAwareness, purchaseIntent, npsScore, featureImportance, etc.)
      - scoring (overallSentimentScore, purchaseReadinessScore, customerSegmentPredicted)
    
    Query examples using VARIANT column:
      SELECT response_payload:result.responseId FROM bronze_qualtrics_survey_responses
      SELECT response_payload:result.answers.npsScore.score FROM bronze_qualtrics_survey_responses
      SELECT response_payload:result.answers.openFeedback.textResponse FROM bronze_qualtrics_survey_responses
    """
    return (
        spark.readStream
            .format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("singleVariantColumn", "response_payload")
            .option("cloudFiles.schemaLocation",VOLUME_BASE_PATH)
            .load(QUALTRICS_RESPONSES_SOURCE_PATH)
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver Layer - Structured Survey Responses with AI-Derived Sentiment
# MAGIC 
# MAGIC Extracts fields from the VARIANT column into a structured table.
# MAGIC Uses Databricks AI Query to derive sentiment classification from survey responses.

# COMMAND ----------

# AI Model endpoint for sentiment analysis
AI_MODEL_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"

@dp.table(
    name="silver_survey_responses",
    comment="Structured survey responses with AI-derived sentiment classification",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true"
    }
)
def silver_survey_responses():
    """
    Extract structured fields from bronze VARIANT column and derive sentiment using AI.
    
    Extracted fields:
    - Response metadata (responseId, surveyId, status, channel)
    - Timestamps (startDate, endDate, duration)
    - Respondent info (customerId, email, name, location)
    - Embedded data (customerSegment, productInterest, campaign)
    - Survey answers (NPS, purchase intent, competitor comparison, open feedback)
    - Pre-calculated scores (sentiment, purchase readiness, predicted segment)
    - AI-derived sentiment classification
    """
    # Helper function to convert Python dict string representation to valid JSON
    # Python uses: single quotes, True, False, None, nan
    # JSON uses: double quotes, true, false, null, null
    # IMPORTANT: Replace structural quotes only, not apostrophes in text (e.g., "I'm", "don't")
    def python_dict_to_json_col(df, col_name: str, output_col: str):
        """Apply chained regexp_replace to convert Python dict string to JSON string.
        
        Uses targeted regex patterns to replace only structural single quotes,
        preserving apostrophes within text values like "I'm" or "don't".
        """
        return (
            df
            # First handle Python literals
            .withColumn(output_col, F.regexp_replace(F.col(col_name), 'nan', 'null'))
            .withColumn(output_col, F.regexp_replace(F.col(output_col), 'True', 'true'))
            .withColumn(output_col, F.regexp_replace(F.col(output_col), 'False', 'false'))
            # Replace structural quotes - patterns where single quote is part of JSON structure
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "\\{'", '{"'))      # {'key -> {"key
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "'\\}", '"}'))      # 'value} -> "value}
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "': '", '": "'))    # ': ' -> ": "
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "', '", '", "'))    # ', ' -> ", "
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "': \\{", '": {'))  # ': { -> ": {
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "': \\[", '": ['))  # ': [ -> ": [
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "'\\]", '"]'))      # '] -> "]
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "\\['", '["'))      # [' -> ["
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "', \\{", '", {'))  # ', { -> ", {
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "', \\[", '", ['))  # ', [ -> ", [
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "':", '":'))        # remaining key endings 'key: -> "key:
            .withColumn(output_col, F.regexp_replace(F.col(output_col), ", '", ', "'))      # remaining , 'value -> , "value
            .withColumn(output_col, F.regexp_replace(F.col(output_col), "': ", '": '))      # 'key': value -> "key": value (numbers)
        )
    
    # Start with the bronze stream
    df = dp.read_stream("bronze_qualtrics_survey_responses")
    
    # Extract response metadata - these are direct STRING fields in result object
    df = (
        df
        .withColumn("response_id", F.expr("response_payload:result:responseId::STRING"))
        .withColumn("survey_id", F.expr("response_payload:result:surveyId::STRING"))
        .withColumn("response_status", F.expr("response_payload:result:responseStatus::STRING"))
        .withColumn("distribution_channel", F.expr("response_payload:result:distributionChannel::STRING"))
        
        # Extract raw Python dict strings from VARIANT
        .withColumn("timestamps_raw", F.expr("response_payload:result:timestamps::STRING"))
        .withColumn("respondent_raw", F.expr("response_payload:result:respondent::STRING"))
        .withColumn("location_raw", F.expr("response_payload:result:locationData::STRING"))
        .withColumn("embedded_raw", F.expr("response_payload:result:embeddedData::STRING"))
        .withColumn("answers_raw", F.expr("response_payload:result:answers::STRING"))
        .withColumn("scoring_raw", F.expr("response_payload:result:scoring::STRING"))
    )
    
    # Convert Python dict strings to valid JSON (handles apostrophes in text)
    df = python_dict_to_json_col(df, "timestamps_raw", "timestamps_json")
    df = python_dict_to_json_col(df, "respondent_raw", "respondent_json")
    df = python_dict_to_json_col(df, "location_raw", "location_json")
    df = python_dict_to_json_col(df, "embedded_raw", "embedded_json")
    df = python_dict_to_json_col(df, "answers_raw", "answers_json")
    df = python_dict_to_json_col(df, "scoring_raw", "scoring_json")
    
    # Parse the JSON strings into VARIANT objects
    df = (
        df
        .withColumn("timestamps_obj", F.expr("parse_json(timestamps_json)"))
        .withColumn("respondent_obj", F.expr("parse_json(respondent_json)"))
        .withColumn("location_obj", F.expr("parse_json(location_json)"))
        .withColumn("embedded_obj", F.expr("parse_json(embedded_json)"))
        .withColumn("answers_obj", F.expr("parse_json(answers_json)"))
        .withColumn("scoring_obj", F.expr("parse_json(scoring_json)"))
    )
    
    # Extract all fields and build final DataFrame
    df = (
        df
        # Extract timestamps from parsed object
        .withColumn("survey_start_date", F.to_timestamp(F.expr("timestamps_obj:startDate::STRING")))
        .withColumn("survey_end_date", F.to_timestamp(F.expr("timestamps_obj:endDate::STRING")))
        .withColumn("recorded_date", F.to_timestamp(F.expr("timestamps_obj:recordedDate::STRING")))
        .withColumn("duration_seconds", F.expr("timestamps_obj:durationSeconds::INT"))
        
        # Extract respondent info from parsed object
        .withColumn("external_customer_id", F.expr("respondent_obj:externalDataReference::STRING"))
        .withColumn("respondent_email", F.expr("respondent_obj:email::STRING"))
        .withColumn("respondent_first_name", F.expr("respondent_obj:firstName::STRING"))
        .withColumn("respondent_last_name", F.expr("respondent_obj:lastName::STRING"))
        
        # Extract location from parsed object
        .withColumn("respondent_city", F.expr("location_obj:city::STRING"))
        .withColumn("respondent_state", F.expr("location_obj:state::STRING"))
        .withColumn("respondent_country", F.expr("location_obj:country::STRING"))
        
        # Extract embedded data from parsed object
        .withColumn("customer_segment", F.expr("embedded_obj:customerSegment::STRING"))
        .withColumn("product_interest", F.expr("embedded_obj:productInterest::STRING"))
        .withColumn("account_id", F.expr("embedded_obj:accountId::STRING"))
        .withColumn("sales_rep_id", F.expr("embedded_obj:salesRepId::STRING"))
        .withColumn("campaign_source", F.expr("embedded_obj:campaignSource::STRING"))
        
        # Extract key survey answers - after parsing answers_obj, nested objects are already VARIANT
        # Access nested fields directly using colon notation
        .withColumn("product_awareness_source", F.expr("answers_obj:productAwareness:selectedChoice::STRING"))
        .withColumn("purchase_intent", F.expr("answers_obj:purchaseIntent:selectedChoice::STRING"))
        .withColumn("purchase_intent_score", F.expr("answers_obj:purchaseIntent:selectedChoiceRecode::INT"))
        .withColumn("nps_score", F.expr("answers_obj:npsScore:score::INT"))
        .withColumn("nps_category", F.expr("answers_obj:npsScore:npsCategory::STRING"))
        .withColumn("price_perception_score", F.expr("answers_obj:pricePerception:value::INT"))
        .withColumn("competitor_comparison", F.expr("answers_obj:competitorComparison:selectedChoice::STRING"))
        .withColumn("competitor_comparison_score", F.expr("answers_obj:competitorComparison:selectedChoiceRecode::INT"))
        .withColumn("open_feedback", F.expr("answers_obj:openFeedback:textResponse::STRING"))
        .withColumn("purchase_timeline", F.expr("answers_obj:purchaseTimeline:selectedChoice::STRING"))
        .withColumn("follow_up_consent", F.expr("answers_obj:followUpConsent:consentGiven::BOOLEAN"))
        
        # Extract pre-calculated scores from parsed scoring object
        .withColumn("calculated_sentiment_score", F.expr("scoring_obj:overallSentimentScore::DOUBLE"))
        .withColumn("purchase_readiness_score", F.expr("scoring_obj:purchaseReadinessScore::INT"))
        .withColumn("predicted_customer_segment", F.expr("scoring_obj:customerSegmentPredicted::STRING"))
        
        # Build AI prompt from survey responses
        .withColumn("ai_sentiment_prompt", 
            F.concat(
                F.lit("Analyze the following customer survey response and classify the overall sentiment as one of: POSITIVE, NEUTRAL, or NEGATIVE. Respond with only the classification.\n\n"),
                F.lit("Product Interest: "), F.coalesce(F.col("product_interest"), F.lit("Not specified")), F.lit("\n"),
                F.lit("NPS Score: "), F.coalesce(F.col("nps_score").cast("string"), F.lit("N/A")), F.lit(" ("), F.coalesce(F.col("nps_category"), F.lit("Unknown")), F.lit(")\n"),
                F.lit("Purchase Intent: "), F.coalesce(F.col("purchase_intent"), F.lit("Not specified")), F.lit("\n"),
                F.lit("Competitor Comparison: "), F.coalesce(F.col("competitor_comparison"), F.lit("Not specified")), F.lit("\n"),
                F.lit("Price Perception Score: "), F.coalesce(F.col("price_perception_score").cast("string"), F.lit("N/A")), F.lit("/100\n"),
                F.lit("Purchase Timeline: "), F.coalesce(F.col("purchase_timeline"), F.lit("Not specified")), F.lit("\n"),
                F.lit("Open Feedback: "), F.coalesce(F.col("open_feedback"), F.lit("No feedback provided")), F.lit("\n")
            )
        )
        
        # Use AI Query to derive sentiment classification
        .withColumn("ai_derived_sentiment",
            F.expr(f"""
                ai_query(
                    '{AI_MODEL_ENDPOINT}',
                    ai_sentiment_prompt
                )
            """)
        )
        
        # Add processing metadata
        .withColumn("processed_at", F.current_timestamp())
    )
    
    # Select final columns (exclude raw payload, intermediate columns, and prompt)
    return df.select(
            "response_id",
            "survey_id",
            "response_status",
            "distribution_channel",
            "survey_start_date",
            "survey_end_date",
            "recorded_date",
            "duration_seconds",
            "external_customer_id",
            "respondent_email",
            "respondent_first_name",
            "respondent_last_name",
            "respondent_city",
            "respondent_state",
            "respondent_country",
            "customer_segment",
            "product_interest",
            "account_id",
            "sales_rep_id",
            "campaign_source",
            "product_awareness_source",
            "purchase_intent",
            "purchase_intent_score",
            "nps_score",
            "nps_category",
            "price_perception_score",
            "competitor_comparison",
            "competitor_comparison_score",
            "open_feedback",
            "purchase_timeline",
            "follow_up_consent",
            "calculated_sentiment_score",
            "purchase_readiness_score",
            "predicted_customer_segment",
            "ai_sentiment_prompt",
            "ai_derived_sentiment",
            "processed_at"
        )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver Layer - AI-Parsed Survey Responses (responseFormat)
# MAGIC 
# MAGIC Alternative silver layer that uses `ai_query` with `responseFormat` to parse
# MAGIC the raw VARIANT payload into a structured schema in a single LLM call.
# MAGIC This replaces manual regex-based Python dict-to-JSON conversion and
# MAGIC field-by-field VARIANT extraction with AI-driven structured output.

# COMMAND ----------

AI_MODEL_ENDPOINT_V2 = "databricks-llama-4-maverick"

RESPONSE_FORMAT_JSON = (
    '{"type": "json_schema", '
    '"json_schema": {'
    '"name": "survey_extraction", '
    '"schema": {'
    '"type": "object", '
    '"properties": {'
    '"response_id": {"type": "string"}, '
    '"survey_id": {"type": "string"}, '
    '"response_status": {"type": "string"}, '
    '"distribution_channel": {"type": "string"}, '
    '"start_date": {"type": "string"}, '
    '"end_date": {"type": "string"}, '
    '"recorded_date": {"type": "string"}, '
    '"duration_seconds": {"type": "string"}, '
    '"external_customer_id": {"type": "string"}, '
    '"respondent_email": {"type": "string"}, '
    '"respondent_first_name": {"type": "string"}, '
    '"respondent_last_name": {"type": "string"}, '
    '"respondent_city": {"type": "string"}, '
    '"respondent_state": {"type": "string"}, '
    '"respondent_country": {"type": "string"}, '
    '"customer_segment": {"type": "string"}, '
    '"product_interest": {"type": "string"}, '
    '"account_id": {"type": "string"}, '
    '"sales_rep_id": {"type": "string"}, '
    '"campaign_source": {"type": "string"}, '
    '"product_awareness_source": {"type": "string"}, '
    '"purchase_intent": {"type": "string"}, '
    '"purchase_intent_score": {"type": "string"}, '
    '"nps_score": {"type": "string"}, '
    '"nps_category": {"type": "string"}, '
    '"price_perception_score": {"type": "string"}, '
    '"competitor_comparison": {"type": "string"}, '
    '"competitor_comparison_score": {"type": "string"}, '
    '"open_feedback": {"type": "string"}, '
    '"purchase_timeline": {"type": "string"}, '
    '"follow_up_consent": {"type": "string"}, '
    '"calculated_sentiment_score": {"type": "string"}, '
    '"purchase_readiness_score": {"type": "string"}, '
    '"predicted_customer_segment": {"type": "string"}, '
    '"ai_derived_sentiment": {"type": "string"}'
    '}}, "strict": true}}'
)

PARSE_SCHEMA = (
    "STRUCT<"
    "response_id: STRING, survey_id: STRING, response_status: STRING, "
    "distribution_channel: STRING, start_date: STRING, end_date: STRING, "
    "recorded_date: STRING, duration_seconds: STRING, external_customer_id: STRING, "
    "respondent_email: STRING, respondent_first_name: STRING, respondent_last_name: STRING, "
    "respondent_city: STRING, respondent_state: STRING, respondent_country: STRING, "
    "customer_segment: STRING, product_interest: STRING, account_id: STRING, "
    "sales_rep_id: STRING, campaign_source: STRING, product_awareness_source: STRING, "
    "purchase_intent: STRING, purchase_intent_score: STRING, nps_score: STRING, "
    "nps_category: STRING, price_perception_score: STRING, competitor_comparison: STRING, "
    "competitor_comparison_score: STRING, open_feedback: STRING, purchase_timeline: STRING, "
    "follow_up_consent: STRING, calculated_sentiment_score: STRING, "
    "purchase_readiness_score: STRING, predicted_customer_segment: STRING, "
    "ai_derived_sentiment: STRING>"
)

@dp.table(
    name="silver_survey_responses_ai_parsed",
    comment="Survey responses parsed via ai_query with responseFormat. "
            "Uses structured output to extract all fields from the raw VARIANT payload in a single LLM call, "
            "replacing manual regex conversion and field-by-field extraction.",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true",
        "delta.feature.variantType-preview" : "supported"
    }
)
def silver_survey_responses_ai_parsed():
    """
    Parse bronze VARIANT payload into structured columns using ai_query with responseFormat.

    Mirrors the tested SQL query: passes response_payload directly to ai_query with
    a json_schema responseFormat, then parses the JSON string output into typed columns.
    """
    df = spark.readStream.table("bronze_qualtrics_survey_responses")

    df = df.withColumn(
        "ai_response",
        F.expr(f"""
            ai_query(
                '{AI_MODEL_ENDPOINT_V2}',
                concat('Extract all fields from this survey response payload. For ai_derived_sentiment, classify as POSITIVE, NEUTRAL, or NEGATIVE.\\n\\n', response_payload),
                responseFormat => '{RESPONSE_FORMAT_JSON}',
                modelParameters => named_struct('max_tokens', 4096, 'temperature', 0.1)
            )
        """)
    )

    df = df.withColumn("parsed", F.from_json(F.col("ai_response"), PARSE_SCHEMA))

    return df.select(
        F.col("parsed.response_id").alias("response_id"),
        F.col("parsed.survey_id").alias("survey_id"),
        F.col("parsed.response_status").alias("response_status"),
        F.col("parsed.distribution_channel").alias("distribution_channel"),
        F.to_timestamp(F.col("parsed.start_date")).alias("survey_start_date"),
        F.to_timestamp(F.col("parsed.end_date")).alias("survey_end_date"),
        F.to_timestamp(F.col("parsed.recorded_date")).alias("recorded_date"),
        F.col("parsed.duration_seconds").cast("int").alias("duration_seconds"),
        F.col("parsed.external_customer_id").alias("external_customer_id"),
        F.col("parsed.respondent_email").alias("respondent_email"),
        F.col("parsed.respondent_first_name").alias("respondent_first_name"),
        F.col("parsed.respondent_last_name").alias("respondent_last_name"),
        F.col("parsed.respondent_city").alias("respondent_city"),
        F.col("parsed.respondent_state").alias("respondent_state"),
        F.col("parsed.respondent_country").alias("respondent_country"),
        F.col("parsed.customer_segment").alias("customer_segment"),
        F.col("parsed.product_interest").alias("product_interest"),
        F.col("parsed.account_id").alias("account_id"),
        F.col("parsed.sales_rep_id").alias("sales_rep_id"),
        F.col("parsed.campaign_source").alias("campaign_source"),
        F.col("parsed.product_awareness_source").alias("product_awareness_source"),
        F.col("parsed.purchase_intent").alias("purchase_intent"),
        F.col("parsed.purchase_intent_score").cast("int").alias("purchase_intent_score"),
        F.col("parsed.nps_score").cast("int").alias("nps_score"),
        F.col("parsed.nps_category").alias("nps_category"),
        F.col("parsed.price_perception_score").cast("int").alias("price_perception_score"),
        F.col("parsed.competitor_comparison").alias("competitor_comparison"),
        F.col("parsed.competitor_comparison_score").cast("int").alias("competitor_comparison_score"),
        F.col("parsed.open_feedback").alias("open_feedback"),
        F.col("parsed.purchase_timeline").alias("purchase_timeline"),
        F.when(F.col("parsed.follow_up_consent").isin("true", "True", "Yes"), True)
         .when(F.col("parsed.follow_up_consent").isin("false", "False", "No"), False)
         .alias("follow_up_consent"),
        F.col("parsed.calculated_sentiment_score").cast("double").alias("calculated_sentiment_score"),
        F.col("parsed.purchase_readiness_score").cast("int").alias("purchase_readiness_score"),
        F.col("parsed.predicted_customer_segment").alias("predicted_customer_segment"),
        F.col("parsed.ai_derived_sentiment").alias("ai_derived_sentiment"),
        F.current_timestamp().alias("processed_at")
    )
