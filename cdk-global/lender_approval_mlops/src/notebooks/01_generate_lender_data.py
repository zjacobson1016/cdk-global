"""
Utility script to generate synthetic lender application data and drop it into
a Unity Catalog volume. Use as a producer for the SDP Auto Loader pipeline.

Run via databricks bundle:
  databricks bundle run lender_approval_mlops -t dev

Or directly with python:
  python src/notebooks/01_generate_lender_data.py --batches 10 --records-per-batch 1500
"""

import argparse
import os
import random
import time
from datetime import datetime, timedelta

import numpy as np
from faker import Faker
from pyspark.sql.types import (
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

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

DEFAULT_CATALOG = os.getenv("CATALOG_NAME", "mfg_mc_se_sa")
DEFAULT_SCHEMA = os.getenv("SCHEMA_NAME", "cdk")
DEFAULT_VOLUME = "raw_data"
DEFAULT_DATA_SUBDIR = "applications"

# ---------------------------------------------------------------------------
# Schema matching the SDP pipeline expectations
# ---------------------------------------------------------------------------
APPLICATION_SCHEMA = StructType([
    StructField("application_id", StringType(), False),
    StructField("application_date", StringType(), False),
    StructField("income", DoubleType(), False),
    StructField("credit_score", IntegerType(), False),
    StructField("employment_years", DoubleType(), False),
    StructField("debt_to_income", DoubleType(), False),
    StructField("loan_amount", DoubleType(), False),
    StructField("loan_purpose", StringType(), False),
    StructField("approved", IntegerType(), False),
])

# Loan purpose distribution (weighted)
LOAN_PURPOSES = ["purchase", "refinance", "home_improvement", "debt_consolidation", "other"]
LOAN_PURPOSE_WEIGHTS = [0.45, 0.25, 0.12, 0.13, 0.05]

# Date range: last 6 months
END_DATE = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
START_DATE = END_DATE - timedelta(days=180)


# ---------------------------------------------------------------------------
# Volume helper
# ---------------------------------------------------------------------------
def ensure_volume(spark, catalog: str, schema: str, volume: str) -> str:
    """Create catalog, schema, and volume if they don't exist. Return base path."""
    #spark.sql(f"CREATE CATALOG IF NOT EXISTS `{catalog}`")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{catalog}`.`{schema}`")
    spark.sql(
        f"CREATE VOLUME IF NOT EXISTS `{catalog}`.`{schema}`.`{volume}` "
        "COMMENT 'Raw lender application landing zone for SDP pipeline.'"
    )
    return f"/Volumes/{catalog}/{schema}/{volume}"


# ---------------------------------------------------------------------------
# Record generators (non-linear distributions)
# ---------------------------------------------------------------------------
def generate_application(fake: Faker, idx: int) -> dict:
    """Generate a single loan application with realistic non-linear distributions."""
    application_id = f"APP-{idx:06d}"
    application_date = fake.date_between(start_date=START_DATE, end_date=END_DATE)

    # Seasonal factor: slight bump mid-year
    month_factor = 1.0 + 0.2 * np.sin((application_date.month - 5) * np.pi / 6)

    # Income: lognormal distribution (right-skewed, realistic salary range)
    income = np.random.lognormal(mean=10.5, sigma=0.6) * 1000 * month_factor
    income = round(float(np.clip(income, 20_000, 350_000)), 2)

    # Credit score: normal distribution centered at 680
    credit_score = int(np.clip(np.random.normal(680, 80), 300, 850))

    # Employment years: exponential distribution (many short tenures, few long)
    employment_years = float(np.random.exponential(scale=4))
    employment_years = round(min(employment_years, 40), 1)

    # Debt-to-income: beta distribution (clustered toward lower values)
    dti = round(float(np.random.beta(2, 5) * 0.5 + 0.1), 3)
    dti = min(dti, 0.95)

    # Loan amount: lognormal
    loan_amount = round(float(np.clip(np.random.lognormal(9, 0.8), 5_000, 500_000)), 2)

    # Loan purpose: weighted categorical
    loan_purpose = np.random.choice(LOAN_PURPOSES, p=LOAN_PURPOSE_WEIGHTS)

    # Approval probability: logistic-style composite score
    score_norm = (credit_score - 300) / 550
    income_norm = (income - 20_000) / 330_000
    dti_bad = 1.0 - dti
    emp_norm = min(employment_years / 10, 1.0)
    approval_prob = 0.2 + 0.5 * score_norm + 0.2 * income_norm + 0.15 * dti_bad + 0.1 * emp_norm
    approval_prob = float(np.clip(approval_prob + np.random.normal(0, 0.08), 0, 1))
    approved = 1 if np.random.random() < approval_prob else 0

    return {
        "application_id": application_id,
        "application_date": application_date.strftime("%Y-%m-%d"),
        "income": income,
        "credit_score": credit_score,
        "employment_years": employment_years,
        "debt_to_income": dti,
        "loan_amount": loan_amount,
        "loan_purpose": str(loan_purpose),
        "approved": approved,
    }


# ---------------------------------------------------------------------------
# Batch writer
# ---------------------------------------------------------------------------
def write_applications_batch(spark, path: str, start_idx: int, batch_size: int):
    """Write a batch of application records to the volume as parquet."""
    fake = Faker()
    Faker.seed(start_idx + int(time.time()))
    np.random.seed(start_idx + int(time.time()))
    random.seed(start_idx + int(time.time()))

    records = [generate_application(fake, start_idx + i) for i in range(batch_size)]
    df = spark.createDataFrame(records, schema=APPLICATION_SCHEMA)
    (
        df.write
        .mode("append")
        .parquet(path)
    )
    print(f"Wrote {batch_size} application records to {path} at {datetime.utcnow().isoformat()}Z")
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Write synthetic lender application data to a UC volume.")
    parser.add_argument("--catalog", default=os.getenv("CATALOG_NAME", DEFAULT_CATALOG))
    parser.add_argument("--schema", dest="schema_", default=os.getenv("SCHEMA_NAME", DEFAULT_SCHEMA))
    parser.add_argument("--volume", default=os.getenv("LENDER_VOLUME", DEFAULT_VOLUME))
    parser.add_argument("--data-subdir", default=os.getenv("LENDER_DATA_SUBDIR", DEFAULT_DATA_SUBDIR))
    parser.add_argument("--records-per-batch", type=int, default=1500)
    parser.add_argument("--batches", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=int, default=2, help="Pause between batches.")
    parser.add_argument("--profile", default=os.getenv("DATABRICKS_PROFILE", "DEFAULT"), help="Databricks CLI profile to use.")
    return parser.parse_args()


def main():
    args = parse_args()

    spark = DatabricksSession.builder.profile(args.profile).serverless().getOrCreate()

    base_path = ensure_volume(spark, args.catalog, args.schema_, args.volume)
    applications_path = f"{base_path}/{args.data_subdir}"

    total_records = args.batches * args.records_per_batch
    print(f"Generating {total_records:,} lender applications → {applications_path}")
    print(f"  Batches: {args.batches}, Records per batch: {args.records_per_batch}")

    next_idx = 0
    for batch in range(args.batches):
        write_applications_batch(spark, applications_path, next_idx, args.records_per_batch)
        next_idx += args.records_per_batch

        if batch < args.batches - 1:
            time.sleep(args.sleep_seconds)

    print(f"\nCompleted writing {total_records:,} lender application records.")


if __name__ == "__main__":
    main()
