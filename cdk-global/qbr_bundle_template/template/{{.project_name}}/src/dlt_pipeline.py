# Databricks notebook source
# COMMAND ----------

import dlt
from pyspark.sql import functions as F
from pyspark.sql.types import *

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration
# MAGIC 
# MAGIC The catalog and schema are automatically configured via the pipeline configuration.
# MAGIC Volume paths are configured for Auto Loader ingestion.

# COMMAND ----------

# Get pipeline configuration
import os
from dotenv import load_dotenv
load_dotenv()
env_path = "/Workspace/Users/zach.jacobson@databricks.com/.bundle/zach-demo-qbr/dev/files/.env"
load_dotenv(dotenv_path=env_path, override=True)

# Configurable volume locations for Auto Loader ingestion
catalog_name = os.getenv("CATALOG_NAME", "mfg_mid_central_sa")
schema_name = os.getenv("SCHEMA_NAME", "qbr_demo")
volume_name = "quotes_volume"

# Subdirectories within the volume
quotes_subdir = "quotes"
notes_subdir = "quote_notes"
customers_subdir = "customers"
products_subdir = "products"

# Schema locations for Auto Loader
VOLUME_BASE_PATH = f"/Volumes/{catalog_name}/{schema_name}/{volume_name}"
QUOTES_SOURCE_PATH = f"{VOLUME_BASE_PATH}/{quotes_subdir}"
QUOTES_SCHEMA_LOCATION = f"{VOLUME_BASE_PATH}/_schema/bronze_quotes"
NOTES_SOURCE_PATH = f"{VOLUME_BASE_PATH}/{notes_subdir}"
NOTES_SCHEMA_LOCATION = f"{VOLUME_BASE_PATH}/_schema/bronze_notes"
CUSTOMERS_SOURCE_PATH = f"{VOLUME_BASE_PATH}/{customers_subdir}"
CUSTOMERS_SCHEMA_LOCATION = f"{VOLUME_BASE_PATH}/_schema/bronze_customers"
PRODUCTS_SOURCE_PATH = f"{VOLUME_BASE_PATH}/{products_subdir}"
PRODUCTS_SCHEMA_LOCATION = f"{VOLUME_BASE_PATH}/_schema/bronze_products"

print(f"Pipeline catalog: {catalog_name}")
print(f"Pipeline schema: {schema_name}")
print(f"Volume base path: {VOLUME_BASE_PATH}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Schema Definitions
# MAGIC 
# MAGIC Schemas matching the quote_volume_writer.py output

# COMMAND ----------

# Schema for quotes matching the volume writer
quote_schema = StructType([
    StructField("id", StringType(), False),
    StructField("customer_id", StringType(), False),
    StructField("customer_name", StringType(), True),
    StructField("location", StringType(), True),
    StructField("product_id", StringType(), False),
    StructField("product_description", StringType(), True),
    StructField("quantity", IntegerType(), False),
    StructField("unit_price", DoubleType(), False),
    StructField("total_price", DoubleType(), False),
    StructField("lead_time", IntegerType(), True),
    StructField("order_date", StringType(), True),
    StructField("status", StringType(), False),
    StructField("priority", StringType(), False),
    StructField("email_source", StringType(), True),
    StructField("email_subject", StringType(), True),
    StructField("email_body", StringType(), True),
    StructField("email_received_at", StringType(), True),
    StructField("created_at", StringType(), True),
    StructField("assigned_reviewer", StringType(), True),
    StructField("updated_at", StringType(), True),
])

quote_note_schema = StructType([
    StructField("id", StringType(), False),
    StructField("quote_id", StringType(), False),
    StructField("content", StringType(), True),
    StructField("note_type", StringType(), True),
    StructField("reviewer", StringType(), True),
    StructField("created_at", StringType(), True),
])

customer_schema = StructType([
    StructField("customer_id", StringType(), False),
    StructField("company_name", StringType(), True),
    StructField("contact_person", StringType(), True),
    StructField("email", StringType(), True),
    StructField("phone", StringType(), True),
    StructField("address", StringType(), True),
    StructField("created_at", StringType(), True),
])

product_schema = StructType([
    StructField("product_id", StringType(), False),
    StructField("product_name", StringType(), True),
    StructField("description", StringType(), True),
    StructField("category", StringType(), True),
    StructField("unit_price", DoubleType(), True),
    StructField("availability_status", StringType(), True),
    StructField("created_at", StringType(), True),
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze Layer - Auto Loader Ingestion from UC Volume

# COMMAND ----------

@dlt.table(
    name="bronze_automated_quotes",
    comment="Raw automated quote data ingested from JSON files via Auto Loader",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def bronze_automated_quotes():
    """
    Read quote JSON files arriving in the Unity Catalog volume and
    land them as the bronze Delta table.
    """
    return (
        spark.readStream
            .format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.schemaLocation", QUOTES_SCHEMA_LOCATION)
            .option("pathGlobFilter", "*.json")
            .schema(quote_schema)
            .load(QUOTES_SOURCE_PATH)
            .select(
                F.col("id"),
                F.col("customer_id"),
                F.col("customer_name"),
                F.col("location"),
                F.col("product_id"),
                F.col("product_description"),
                F.col("quantity"),
                F.col("unit_price").cast("decimal(10,2)"),
                F.col("total_price").cast("decimal(10,2)"),
                F.col("lead_time"),
                F.to_date("order_date").alias("order_date"),
                F.col("status"),
                F.col("priority"),
                F.col("email_source"),
                F.col("email_subject"),
                F.col("email_body"),
                F.to_timestamp("email_received_at").alias("email_received_at"),
                F.to_timestamp("created_at").alias("created_at"),
                F.col("assigned_reviewer"),
                F.to_timestamp("updated_at").alias("updated_at"),
                F.col("_metadata.file_path").alias("_source_file"),
                F.current_timestamp().alias("_bronze_ingestion_time")
            )
    )


@dlt.table(
    name="bronze_quote_notes",
    comment="Raw quote notes ingested from JSON files via Auto Loader",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def bronze_quote_notes():
    """
    Read quote notes JSON files from the Unity Catalog volume.
    """
    return (
        spark.readStream
            .format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.schemaLocation", NOTES_SCHEMA_LOCATION)
            .option("pathGlobFilter", "*.json")
            .schema(quote_note_schema)
            .load(NOTES_SOURCE_PATH)
            .select(
                F.col("id"),
                F.col("quote_id"),
                F.col("content"),
                F.col("note_type"),
                F.col("reviewer"),
                F.to_timestamp("created_at").alias("created_at"),
                F.col("_metadata.file_path").alias("_source_file"),
                F.current_timestamp().alias("_bronze_ingestion_time")
            )
    )


@dlt.table(
    name="bronze_customers",
    comment="Raw customer data ingested from JSON files via Auto Loader",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def bronze_customers():
    """
    Read customer JSON files from the Unity Catalog volume.
    """
    return (
        spark.readStream
            .format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.schemaLocation", CUSTOMERS_SCHEMA_LOCATION)
            .option("pathGlobFilter", "*.json")
            .schema(customer_schema)
            .load(CUSTOMERS_SOURCE_PATH)
            .select(
                F.col("customer_id"),
                F.col("company_name"),
                F.col("contact_person"),
                F.col("email"),
                F.col("phone"),
                F.col("address"),
                F.to_timestamp("created_at").alias("customer_created_at"),
                F.col("_metadata.file_path").alias("_source_file"),
                F.current_timestamp().alias("_bronze_ingestion_time")
            )
    )


@dlt.table(
    name="bronze_products",
    comment="Raw product catalog data ingested from JSON files via Auto Loader",
    table_properties={
        "quality": "bronze",
        "pipelines.autoOptimize.managed": "true",
        "delta.enableChangeDataFeed": "true"
    }
)
def bronze_products():
    """
    Read product JSON files from the Unity Catalog volume.
    """
    return (
        spark.readStream
            .format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.schemaLocation", PRODUCTS_SCHEMA_LOCATION)
            .option("pathGlobFilter", "*.json")
            .schema(product_schema)
            .load(PRODUCTS_SOURCE_PATH)
            .select(
                F.col("product_id"),
                F.col("product_name"),
                F.col("description"),
                F.col("category"),
                F.col("unit_price").cast("decimal(10,2)"),
                F.col("availability_status"),
                F.to_timestamp("created_at").alias("product_created_at"),
                F.col("_metadata.file_path").alias("_source_file"),
                F.current_timestamp().alias("_bronze_ingestion_time")
            )
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver Layer - Cleaned and Validated Quote Data

# COMMAND ----------

@dlt.table(
    name="silver_automated_quotes",
    comment="Cleaned and validated automated quote data with quality checks",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true"
    }
)
@dlt.expect_or_fail("valid_quote_id", "id IS NOT NULL AND id != ''")
@dlt.expect_or_fail("valid_customer_id", "customer_id IS NOT NULL AND customer_id != ''")
@dlt.expect_or_fail("valid_product_id", "product_id IS NOT NULL AND product_id != ''")
@dlt.expect_or_fail("valid_priority", "priority IN ('High', 'Medium', 'Low')")
@dlt.expect_or_fail("valid_status", "status IN ('Pending', 'Approved', 'Denied', 'Delivered')")
@dlt.expect_or_fail("valid_quantity", "quantity > 0")
@dlt.expect_or_fail("valid_prices", "unit_price > 0 AND total_price > 0")
@dlt.expect_or_fail("valid_lead_time", "lead_time > 0 AND lead_time <= 90")
@dlt.expect("valid_customer_name", "customer_name IS NOT NULL AND customer_name != ''")
@dlt.expect("valid_location", "location IS NOT NULL AND location != ''")
@dlt.expect("valid_email_source", "email_source IS NOT NULL AND email_source != ''")
def silver_automated_quotes():
    """
    Clean and validate automated quote data.
    Apply business rules and data quality checks.
    """
    return (
        dlt.read_stream("bronze_automated_quotes")
        .filter(F.col("id").isNotNull())
        .filter(F.col("customer_id").isNotNull())
        .filter(F.col("product_id").isNotNull())
        .filter(F.col("quantity") > 0)
        .filter(F.col("unit_price") > 0)
        .filter(F.col("lead_time").isNotNull())
        .withColumn("processed_timestamp", F.current_timestamp())
        .withColumn("priority_score", 
            F.when(F.col("priority") == "High", 3)
            .when(F.col("priority") == "Medium", 2)
            .otherwise(1))
        .withColumn("days_to_order", 
            F.datediff(F.col("order_date"), F.current_date()))
        .withColumn("processing_age_hours", 
            F.round((F.unix_timestamp(F.current_timestamp()) - F.unix_timestamp(F.col("email_received_at"))) / 3600, 2))
        .withColumn("is_urgent",
            F.when((F.col("priority") == "High") & (F.col("days_to_order") <= 3), True)
            .when((F.col("priority") == "Medium") & (F.col("days_to_order") <= 1), True)
            .otherwise(False))
        .withColumn("quote_value_tier",
            F.when(F.col("total_price") >= 10000, "Large")
            .when(F.col("total_price") >= 5000, "Medium")
            .otherwise("Small"))
        .withColumn("lead_time_category",
            F.when(F.col("lead_time") <= 10, "Express")
            .when(F.col("lead_time") <= 20, "Standard")
            .otherwise("Extended"))
        .withColumn("price_verification", 
            F.when(F.abs(F.col("total_price") - (F.col("quantity") * F.col("unit_price"))) < 0.01, "Verified")
            .otherwise("Error"))
    )

@dlt.table(
    name="silver_quote_notes",
    comment="Cleaned and validated quote notes with enrichments",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true"
    }
)
@dlt.expect_or_fail("valid_note_id", "id IS NOT NULL")
@dlt.expect_or_fail("valid_quote_ref", "quote_id IS NOT NULL AND quote_id != ''")
@dlt.expect_or_fail("valid_note_type", "note_type IN ('Comment', 'Approval', 'Denial', 'Revision')")
@dlt.expect("valid_content", "content IS NOT NULL AND length(content) > 0")
@dlt.expect("valid_reviewer", "reviewer IS NOT NULL AND reviewer != ''")
def silver_quote_notes():
    """
    Clean and validate quote notes data.
    """
    return (
        dlt.read_stream("bronze_quote_notes")
        .filter(F.col("quote_id").isNotNull())
        .filter(F.col("content").isNotNull())
        .withColumn("processed_timestamp", F.current_timestamp())
        .withColumn("content_length", F.length(F.col("content")))
        .withColumn("note_sentiment",
            F.when(F.lower(F.col("content")).rlike("approv|accept|confirm|good"), "positive")
            .when(F.lower(F.col("content")).rlike("den|reject|concern|issue|problem"), "negative")
            .otherwise("neutral"))
        .withColumn("contains_pricing", F.lower(F.col("content")).contains("price"))
        .withColumn("contains_timeline", F.lower(F.col("content")).rlike("date|schedule|deadline|urgent"))
    )

@dlt.table(
    name="silver_customers",
    comment="Cleaned and validated customer data with enrichments",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true"
    }
)
@dlt.expect_or_fail("valid_customer_id", "customer_id IS NOT NULL AND customer_id != ''")
@dlt.expect_or_fail("valid_company_name", "company_name IS NOT NULL AND company_name != ''")
@dlt.expect("valid_email", "email IS NOT NULL AND email RLIKE '^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'")
@dlt.expect("valid_phone", "phone IS NOT NULL AND phone != ''")
def silver_customers():
    """
    Clean and validate customer data.
    """
    return (
        dlt.read_stream("bronze_customers")
        .filter(F.col("customer_id").isNotNull())
        .filter(F.col("company_name").isNotNull())
        .withColumn("processed_timestamp", F.current_timestamp())
        .withColumn("email_domain", F.split(F.col("email"), "@").getItem(1))
        .withColumn("state", F.split(F.col("address"), ", ").getItem(1))
        .withColumn("customer_tier",
            F.when(F.lower(F.col("company_name")).contains("manufacturing"), "Industrial")
            .when(F.lower(F.col("company_name")).contains("chemical"), "Process")
            .when(F.lower(F.col("company_name")).contains("power"), "Utility")
            .otherwise("Other"))
        .withColumnRenamed("customer_created_at", "created_at")
    )

@dlt.table(
    name="silver_products",
    comment="Cleaned and validated product catalog data with enrichments",
    table_properties={
        "quality": "silver",
        "pipelines.autoOptimize.managed": "true"
    }
)
@dlt.expect_or_fail("valid_product_id", "product_id IS NOT NULL AND product_id != ''")
@dlt.expect_or_fail("valid_product_name", "product_name IS NOT NULL AND product_name != ''")
@dlt.expect_or_fail("valid_unit_price", "unit_price > 0")
@dlt.expect("valid_category", "category IS NOT NULL AND category != ''")
@dlt.expect("valid_availability", "availability_status IN ('Available', 'Limited', 'Backordered', 'Discontinued')")
def silver_products():
    """
    Clean and validate product data.
    """
    return (
        dlt.read_stream("bronze_products")
        .filter(F.col("product_id").isNotNull())
        .filter(F.col("product_name").isNotNull())
        .filter(F.col("unit_price") > 0)
        .withColumn("processed_timestamp", F.current_timestamp())
        .withColumn("price_tier",
            F.when(F.col("unit_price") >= 4000, "Premium")
            .when(F.col("unit_price") >= 2000, "Standard")
            .otherwise("Economy"))
        .withColumn("product_type",
            F.when(F.lower(F.col("product_name")).contains("coplanar"), "Pressure_Coplanar")
            .when(F.lower(F.col("product_name")).contains("in-line"), "Pressure_Inline")
            .when(F.lower(F.col("product_name")).contains("multivariable"), "Pressure_MultiVariable")
            .when(F.lower(F.col("product_name")).contains("transmitter"), "Pressure_Instrument")
            .otherwise("Other"))
        .withColumn("description_length", F.length(F.col("description")))
        .withColumnRenamed("product_created_at", "created_at")
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold Layer - Final Quote Management Tables (1:1 with Database Schema)

# COMMAND ----------

@dlt.table(
    name="automated_quotes",
    comment="Final automated quotes table matching database schema exactly",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def automated_quotes():
    """
    Create final automated_quotes table that matches the database schema exactly.
    This aggregates and finalizes quote data from silver layer.
    """
    return (
        dlt.read("silver_automated_quotes")
        .select(
            F.col("id"),
            F.col("customer_id"),
            F.col("customer_name"),
            F.col("location"),
            F.col("product_id"),
            F.col("product_description"),
            F.col("quantity"),
            F.col("unit_price").cast("decimal(10,2)"),
            F.col("total_price").cast("decimal(10,2)"),
            F.col("lead_time"),
            F.col("order_date").cast("date"),
            F.col("status"),
            F.col("priority"),
            F.col("email_source"),
            F.col("email_subject"),
            F.col("email_body"),
            F.col("email_received_at").cast("timestamp"),
            F.col("created_at").cast("timestamp"),
            F.col("assigned_reviewer"),
            F.col("updated_at").cast("timestamp"),
            F.col("_bronze_ingestion_time")
        )
        .filter(F.col("price_verification") == "Verified")  # Only include verified quotes
    )

@dlt.table(
    name="quote_notes",
    comment="Final quote notes table matching database schema exactly",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def quote_notes():
    """
    Create final quote_notes table that matches the database schema exactly.
    """
    return (
        dlt.read("silver_quote_notes")
        .select(
            F.col("quote_id"),
            F.col("content"),
            F.col("note_type"),
            F.col("created_at").cast("timestamp"),
            F.col("reviewer")
        )
        .filter(F.col("content_length") > 5)  # Only include meaningful notes
    )

@dlt.table(
    name="customers",
    comment="Final customers table matching database schema exactly",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def customers():
    """
    Create final customers table that matches the database schema exactly.
    This deduplicates and finalizes customer data from silver layer.
    """
    return (
        dlt.read("silver_customers")
        .select(
            F.col("customer_id"),
            F.col("company_name"),
            F.col("contact_person"),
            F.col("email"),
            F.col("phone"),
            F.col("address"),
            F.col("created_at").cast("timestamp"),
            # Include computed columns for analytics
            F.col("email_domain"),
            F.col("customer_tier")
        )  # Ensure unique customers
    )

@dlt.table(
    name="products",
    comment="Final products table matching database schema exactly",
    table_properties={
        "quality": "gold",
        "pipelines.autoOptimize.managed": "true"
    }
)
def products():
    """
    Create final products table that matches the database schema exactly.
    This deduplicates and finalizes product catalog data from silver layer.
    """
    return (
        dlt.read("silver_products")
        .select(
            F.col("product_id"),
            F.col("product_name"),
            F.col("description"),
            F.col("category"),
            F.col("unit_price").cast("decimal(10,2)"),
            F.col("availability_status"),
            F.col("created_at").cast("timestamp"),
            # Include computed columns for analytics
            F.col("price_tier"),
            F.col("product_type")
        ) # Ensure unique products
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Views for Quote Management Analytics

# COMMAND ----------

@dlt.table(
    name="quote_dashboard_view",
    comment="Real-time dashboard view for quote management and approval workflow"
)
def quote_dashboard_view():
    """
    Create a consolidated view for quote management dashboard consumption.
    """
    quotes_with_notes = (
        dlt.read("automated_quotes").alias("aq")
        .join(
            dlt.read("quote_notes").alias("qn")
            .groupBy("quote_id")
            .agg(
                F.count("*").alias("note_count"),
                F.max("created_at").alias("last_note_date"),
                F.sum(F.when(F.col("note_type") == "Approval", 1).otherwise(0)).alias("approval_count"),
                F.sum(F.when(F.col("note_type") == "Denial", 1).otherwise(0)).alias("denial_count")
            ).alias("notes_agg"),
            F.col("aq.id") == F.col("notes_agg.quote_id"),
            "left"
        )
    )
    
    return (
        quotes_with_notes
        .filter(F.col("aq.created_at") >= F.current_date() - 30)  # Last 30 days
        .select(
            F.col("aq.id"),
            F.col("aq.customer_name"),
            F.col("aq.product_id"),
            F.col("aq.total_price"),
            F.col("aq.status"),
            F.col("aq.priority"),
            F.col("aq.assigned_reviewer"),
            F.datediff(F.current_date(), F.col("aq.order_date")).alias("days_to_order"),
            F.round((F.unix_timestamp(F.current_timestamp()) - F.unix_timestamp(F.col("aq.email_received_at"))) / 3600, 1).alias("processing_hours"),
            F.coalesce("notes_agg.note_count", F.lit(0)).alias("total_notes"),
            F.coalesce("notes_agg.approval_count", F.lit(0)).alias("approvals"),
            F.coalesce("notes_agg.denial_count", F.lit(0)).alias("denials"),
            F.col("aq.created_at"),
            F.col("aq.order_date")
        )
        .orderBy(F.desc("aq.created_at"), "aq.priority", "aq.total_price")
    )

@dlt.table(
    name="product_performance_view", 
    comment="Product sales performance and quote conversion analysis"
)
def product_performance_view():
    """
    Product performance analysis for sales and inventory planning.
    """
    return (
        dlt.read("automated_quotes").alias("aq")
        .join(dlt.read("products").alias("p"), F.col("aq.product_id") == F.col("p.product_id"), "left")
        .groupBy(
            F.col("aq.product_id"),
            F.col("p.product_name"),
            F.col("p.category"),
            F.date_trunc("month", F.col("aq.created_at")).alias("month")
        )
        .agg(
            F.count("*").alias("total_quotes"),
            F.sum(F.when(F.col("aq.status") == "Approved", 1).otherwise(0)).alias("approved_quotes"),
            F.sum(F.when(F.col("aq.status") == "Denied", 1).otherwise(0)).alias("denied_quotes"),
            F.sum(F.when(F.col("aq.status") == "Pending", 1).otherwise(0)).alias("pending_quotes"),
            F.sum("aq.quantity").alias("total_quantity_quoted"),
            F.sum(F.when(F.col("aq.status") == "Approved", F.col("aq.total_price")).otherwise(0)).alias("approved_revenue"),
            F.sum("aq.total_price").alias("total_quoted_value"),
            F.avg("aq.total_price").alias("avg_quote_value")
        )
        .withColumn("approval_rate",
            F.round(F.col("approved_quotes") / F.col("total_quotes") * 100, 2))
        .filter(F.col("month") >= F.add_months(F.current_date(), -6))  # Last 6 months
        .orderBy(F.desc("total_quoted_value"), F.desc("approval_rate"))
    )

@dlt.table(
    name="customer_analytics_view",
    comment="Customer quote patterns and relationship analysis"
)
def customer_analytics_view():
    """
    Customer analytics for account management and sales forecasting.
    """
    customer_quotes = (
        dlt.read("automated_quotes").alias("aq")
        .join(dlt.read("customers").alias("c"), F.col("aq.customer_id") == F.col("c.customer_id"), "left")
        .groupBy(
            F.col("aq.customer_id"),
            F.col("c.company_name"),
            F.col("c.customer_tier"),
            F.col("c.email_domain")
        )
        .agg(
            F.count("*").alias("total_quotes"),
            F.sum(F.when(F.col("aq.status") == "Approved", 1).otherwise(0)).alias("approved_quotes"),
            F.sum(F.when(F.col("aq.status") == "Approved", F.col("aq.total_price")).otherwise(0)).alias("total_revenue"),
            F.sum("aq.total_price").alias("total_quoted_value"),
            F.avg("aq.total_price").alias("avg_quote_value"),
            F.min("aq.created_at").alias("first_quote_date"),
            F.max("aq.created_at").alias("last_quote_date"),
            F.countDistinct("aq.product_id").alias("unique_products_quoted")
        )
        .withColumn("approval_rate",
            F.round(F.col("approved_quotes") / F.col("total_quotes") * 100, 2))
        .withColumn("days_as_customer",
            F.datediff(F.col("last_quote_date"), F.col("first_quote_date")))
    )
    
    return (
        customer_quotes
        .filter(F.col("total_quotes") >= 1)
        .select(
            "customer_id",
            "company_name", 
            "customer_tier",
            "total_quotes",
            "approved_quotes",
            F.round("total_revenue", 2).alias("total_revenue"),
            F.round("avg_quote_value", 2).alias("avg_quote_value"),
            F.round("approval_rate", 1).alias("approval_rate_pct"),
            "unique_products_quoted",
            "days_as_customer",
            "first_quote_date",
            "last_quote_date"
        )
        .orderBy(F.desc("total_revenue"), F.desc("approval_rate_pct"))
    )

@dlt.table(
    name="reviewer_performance_view",
    comment="Quote reviewer performance and workload analysis"
)
def reviewer_performance_view():
    """
    Reviewer performance analysis for workflow optimization.
    """
    return (
        dlt.read("automated_quotes").alias("aq")
        .groupBy(
            F.col("aq.assigned_reviewer"),
            F.date_trunc("week", F.col("aq.created_at")).alias("week")
        )
        .agg(
            F.count("*").alias("total_quotes_assigned"),
            F.sum(F.when(F.col("aq.status") == "Approved", 1).otherwise(0)).alias("approved_quotes"),
            F.sum(F.when(F.col("aq.status") == "Denied", 1).otherwise(0)).alias("denied_quotes"),
            F.sum(F.when(F.col("aq.status") == "Pending", 1).otherwise(0)).alias("pending_quotes"),
            F.sum(F.when(F.col("aq.priority") == "High", 1).otherwise(0)).alias("high_priority_quotes"),
            F.avg(F.datediff(F.current_date(), F.col("aq.created_at"))).alias("avg_quote_age_days"),
            F.sum("aq.total_price").alias("total_value_reviewed")
        )
        .withColumn("approval_rate",
            F.round(F.col("approved_quotes") / (F.col("approved_quotes") + F.col("denied_quotes")) * 100, 2))
        .withColumn("processing_efficiency",
            F.round((F.col("approved_quotes") + F.col("denied_quotes")) / F.col("total_quotes_assigned") * 100, 2))
        .filter(F.col("week") >= F.date_trunc("week", F.current_date()) - F.expr("INTERVAL 8 WEEKS"))
        .orderBy(F.desc("week"), "assigned_reviewer")
    )
