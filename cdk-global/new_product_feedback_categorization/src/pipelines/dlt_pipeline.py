# Databricks notebook source
# COMMAND ----------

import dlt
from pyspark.sql import functions as F

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration
# MAGIC 
# MAGIC The catalog and schema are automatically configured via the pipeline configuration.
# MAGIC Volume paths are configured for Auto Loader ingestion of Qualtrics survey responses.

# COMMAND ----------

# Get pipeline configuration
import os
from dotenv import load_dotenv
env_path = "/Workspace/Users/zach.jacobson@databricks.com/.bundle/new_product_feedback_categorization/dev/files/.env"
load_dotenv(dotenv_path=env_path, override=True)

# Configurable volume locations for Auto Loader ingestion
catalog_name = os.getenv("CATALOG_NAME", "mfg_mc_se_sa")
schema_name = os.getenv("SCHEMA_NAME", "cdk")
volume_name = os.getenv("VOLUME_FOLDER_NAME", "survey_responses")

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

@dlt.table(
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

@dlt.table(
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
    df = dlt.read_stream("bronze_qualtrics_survey_responses")
    
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
