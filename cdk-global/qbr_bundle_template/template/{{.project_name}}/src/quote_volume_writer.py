"""
Utility script to drop quote JSON files into a Unity Catalog volume.
Use as a lightweight producer for the DLT Auto Loader pipeline.

Run via databricks bundle:
  databricks bundle run quote_volume_writer -t dev

Or directly with python:
  python src/quote_volume_writer.py --batches 20 --records-per-batch 25
"""

import argparse
import os
import random
import time
from datetime import datetime, timedelta

from faker import Faker
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)
from databricks.connect import DatabricksSession
from dotenv import load_dotenv
load_dotenv()
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
DEFAULT_CATALOG = os.getenv("CATALOG_NAME")
DEFAULT_SCHEMA = os.getenv("SCHEMA_NAME")
DEFAULT_VOLUME = "quotes_volume"
DEFAULT_DATA_SUBDIR = "quotes"
DEFAULT_NOTES_SUBDIR = "quote_notes"
DEFAULT_CUSTOMERS_SUBDIR = "customers"
DEFAULT_PRODUCTS_SUBDIR = "products"

# Schema matching the DLT pipeline expectations
QUOTE_SCHEMA = StructType([
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

QUOTE_NOTE_SCHEMA = StructType([
    StructField("id", StringType(), False),
    StructField("quote_id", StringType(), False),
    StructField("content", StringType(), True),
    StructField("note_type", StringType(), True),
    StructField("reviewer", StringType(), True),
    StructField("created_at", StringType(), True),
])

CUSTOMER_SCHEMA = StructType([
    StructField("customer_id", StringType(), False),
    StructField("company_name", StringType(), True),
    StructField("contact_person", StringType(), True),
    StructField("email", StringType(), True),
    StructField("phone", StringType(), True),
    StructField("address", StringType(), True),
    StructField("created_at", StringType(), True),
])

PRODUCT_SCHEMA = StructType([
    StructField("product_id", StringType(), False),
    StructField("product_name", StringType(), True),
    StructField("description", StringType(), True),
    StructField("category", StringType(), True),
    StructField("unit_price", DoubleType(), True),
    StructField("availability_status", StringType(), True),
    StructField("created_at", StringType(), True),
])

# Product templates for realistic data generation
PRODUCT_PREFIXES = ["3051S-CP", "3051S-IL", "3051S-MV", "2088-GP", "2088-AB", "3144P", "2051C", "3051S-TG"]
PRODUCT_TYPES = [
    "Coplanar Pressure Transmitter with 4-20mA output",
    "In-Line Pressure Transmitter with HART protocol",
    "MultiVariable Transmitter for flow measurement",
    "Gage Pressure Transmitter with digital display",
    "Absolute Pressure Transmitter with LCD",
    "Temperature Transmitter with dual input",
    "Coplanar Pressure Transmitter compact design",
    "Temperature Transmitter with wireless capability"
]

REVIEWERS = [
    "sarah.johnson@iotautomation.com",
    "mike.davis@iotautomation.com",
    "jennifer.smith@iotautomation.com"
]

NOTE_CONTENT_TEMPLATES = {
    "High": "Quote pricing verified and approved",
    "Approved": "Customer credit check completed",
    "Pending": "Product availability confirmed",
    "default": "Additional technical review required"
}


def ensure_volume(spark: DatabricksSession, catalog: str, schema: str, volume: str) -> str:
    """Create the volume if it doesn't exist and return the base path."""
    spark.sql(
        f"CREATE VOLUME IF NOT EXISTS `{catalog}`.`{schema}`.`{volume}` "
        "COMMENT 'Raw quote JSON landing zone for DLT pipeline.'"
    )
    base_path = f"/Volumes/{catalog}/{schema}/{volume}"
    return base_path


def generate_quote(fake: Faker, idx: int) -> dict:
    """Generate a single quote record."""
    product_type_idx = random.randint(0, len(PRODUCT_PREFIXES) - 1)
    product_prefix = PRODUCT_PREFIXES[product_type_idx]
    
    customer_id = f"CUST-{idx:08d}"
    customer_name = fake.company()
    product_id = f"{product_prefix}-{idx:06d}"
    product_description = f"Rosemount {product_prefix} {PRODUCT_TYPES[product_type_idx]}"
    location = f"{fake.building_number()} {fake.street_name()} {fake.city()} {fake.state_abbr()}"
    
    quantity = random.randint(1, 10)
    unit_price = round(random.uniform(2000, 5000), 2)
    total_price = round(quantity * unit_price, 2)
    lead_time = random.randint(5, 45)
    
    # Status with weighted distribution
    rand_val = random.random()
    if rand_val < 0.70:
        status = "Approved"
    elif rand_val < 0.85:
        status = "Pending"
    else:
        status = "Denied"
    
    priority = random.choice(["High", "Medium", "Low"])
    
    if random.random() < 0.1:
        email_source = "zach.jacobson@databricks.com"
    else:
        email_source = fake.company_email()
    
    assigned_reviewer = random.choice(REVIEWERS)
    
    created_at = fake.date_time_this_month()
    order_date = (datetime.now() + timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
    
    return {
        "id": f"QT-{idx:08d}",
        "customer_id": customer_id,
        "customer_name": customer_name,
        "location": location,
        "product_id": product_id,
        "product_description": product_description,
        "quantity": quantity,
        "unit_price": unit_price,
        "total_price": total_price,
        "lead_time": lead_time,
        "order_date": order_date,
        "status": status,
        "priority": priority,
        "email_source": email_source,
        "email_subject": f"Quote Request - {product_id} - {customer_name}",
        "email_body": "Please quote options for IoT sensor codes and transmitters",
        "email_received_at": created_at.isoformat(),
        "created_at": created_at.isoformat(),
        "assigned_reviewer": assigned_reviewer,
        "updated_at": created_at.isoformat(),
    }


def generate_quote_note(fake: Faker, quote: dict, note_idx: int) -> dict:
    """Generate a quote note based on the quote."""
    priority = quote["priority"]
    status = quote["status"]
    
    if priority == "High":
        content = NOTE_CONTENT_TEMPLATES["High"]
        note_type = "Comment"
    elif status == "Approved":
        content = NOTE_CONTENT_TEMPLATES["Approved"]
        note_type = "Approval"
    elif status == "Pending":
        content = NOTE_CONTENT_TEMPLATES["Pending"]
        note_type = "Revision"
    else:
        content = NOTE_CONTENT_TEMPLATES["default"]
        note_type = "Denial"
    
    return {
        "id": f"NOTE-{note_idx:08d}",
        "quote_id": quote["id"],
        "content": content,
        "note_type": note_type,
        "reviewer": quote.get("assigned_reviewer", "Sarah Johnson"),
        "created_at": quote["created_at"],
    }


def generate_customer(fake: Faker, quote: dict) -> dict:
    """Generate a customer record from a quote."""
    email = quote["email_source"]
    contact_person = email.split("@")[0] if "@" in email else "Unknown"
    
    return {
        "customer_id": quote["customer_id"],
        "company_name": quote["customer_name"],
        "contact_person": contact_person,
        "email": email,
        "phone": "555-0000",
        "address": quote["location"],
        "created_at": quote["created_at"],
    }


def generate_product(fake: Faker, quote: dict) -> dict:
    """Generate a product record from a quote."""
    return {
        "product_id": quote["product_id"],
        "product_name": quote["product_description"],
        "description": quote["product_description"],
        "category": "IoT Sensors",
        "unit_price": quote["unit_price"],
        "availability_status": "Available",
        "created_at": quote["created_at"],
    }


def write_quotes_batch(spark: DatabricksSession, path: str, start_idx: int, batch_size: int):
    """Write a batch of quote records to the volume."""
    fake = Faker()
    Faker.seed(start_idx + int(time.time()))
    random.seed(start_idx + int(time.time()))
    
    records = [generate_quote(fake, start_idx + i) for i in range(batch_size)]
    df = spark.createDataFrame(records, schema=QUOTE_SCHEMA)
    (
        df.write
        .mode("append")
        .option("compression", "none")
        .json(path)
    )
    print(f"Wrote {batch_size} quote records to {path} at {datetime.utcnow().isoformat()}Z")
    return records


def write_notes_batch(spark: DatabricksSession, path: str, quotes: list, start_idx: int):
    """Write quote notes for a batch of quotes."""
    fake = Faker()
    notes = [generate_quote_note(fake, q, start_idx + i) for i, q in enumerate(quotes)]
    df = spark.createDataFrame(notes, schema=QUOTE_NOTE_SCHEMA)
    (
        df.write
        .mode("append")
        .option("compression", "none")
        .json(path)
    )
    print(f"Wrote {len(notes)} note records to {path}")


def write_customers_batch(spark: DatabricksSession, path: str, quotes: list):
    """Write customer records for a batch of quotes."""
    fake = Faker()
    customers = [generate_customer(fake, q) for q in quotes]
    df = spark.createDataFrame(customers, schema=CUSTOMER_SCHEMA)
    (
        df.write
        .mode("append")
        .option("compression", "none")
        .json(path)
    )
    print(f"Wrote {len(customers)} customer records to {path}")


def write_products_batch(spark: DatabricksSession, path: str, quotes: list):
    """Write product records for a batch of quotes."""
    fake = Faker()
    products = [generate_product(fake, q) for q in quotes]
    df = spark.createDataFrame(products, schema=PRODUCT_SCHEMA)
    (
        df.write
        .mode("append")
        .option("compression", "none")
        .json(path)
    )
    print(f"Wrote {len(products)} product records to {path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Write quote JSON files to a UC volume.")
    parser.add_argument("--catalog", default=os.getenv("QUOTE_CATALOG", DEFAULT_CATALOG))
    parser.add_argument("--schema", dest="schema_", default=os.getenv("QUOTE_SCHEMA", DEFAULT_SCHEMA))
    parser.add_argument("--volume", default=os.getenv("QUOTE_VOLUME", DEFAULT_VOLUME))
    parser.add_argument("--data-subdir", default=os.getenv("QUOTE_DATA_SUBDIR", DEFAULT_DATA_SUBDIR))
    parser.add_argument("--notes-subdir", default=os.getenv("QUOTE_NOTES_SUBDIR", DEFAULT_NOTES_SUBDIR))
    parser.add_argument("--customers-subdir", default=os.getenv("QUOTE_CUSTOMERS_SUBDIR", DEFAULT_CUSTOMERS_SUBDIR))
    parser.add_argument("--products-subdir", default=os.getenv("QUOTE_PRODUCTS_SUBDIR", DEFAULT_PRODUCTS_SUBDIR))
    parser.add_argument("--records-per-batch", type=int, default=10)
    parser.add_argument("--batches", type=int, default=5)
    parser.add_argument("--sleep-seconds", type=int, default=5, help="Pause between batches.")
    parser.add_argument("--include-notes", action="store_true", default=True, help="Also write quote notes.")
    parser.add_argument("--include-customers", action="store_true", default=True, help="Also write customers.")
    parser.add_argument("--include-products", action="store_true", default=True, help="Also write products.")
    parser.add_argument("--profile", default=os.getenv("DATABRICKS_PROFILE", "DEFAULT"), help="Databricks CLI profile to use.")
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Use DatabricksSession for Databricks Connect
    # Default to serverless so bundle runs don't require a cluster_id in ~/.databrickscfg
    spark = DatabricksSession.builder.profile("dogfood1").serverless().getOrCreate()

    base_path = ensure_volume(spark, args.catalog, args.schema_, args.volume)
    quotes_path = f"{base_path}/{args.data_subdir}"
    notes_path = f"{base_path}/{args.notes_subdir}"
    customers_path = f"{base_path}/{args.customers_subdir}"
    products_path = f"{base_path}/{args.products_subdir}"

    print(f"Writing JSON files to {quotes_path}")
    print(f"  Batches: {args.batches}, Records per batch: {args.records_per_batch}")

    next_idx = 0
    note_idx = 0
    
    for batch in range(args.batches):
        # Write quotes
        quotes = write_quotes_batch(spark, quotes_path, next_idx, args.records_per_batch)
        
        # Write related records
        if args.include_notes:
            write_notes_batch(spark, notes_path, quotes, note_idx)
            note_idx += len(quotes)
        
        if args.include_customers:
            write_customers_batch(spark, customers_path, quotes)
        
        if args.include_products:
            write_products_batch(spark, products_path, quotes)
        
        next_idx += args.records_per_batch
        
        if batch < args.batches - 1:
            time.sleep(args.sleep_seconds)

    print("Completed writing quote JSON files.")


if __name__ == "__main__":
    main()

