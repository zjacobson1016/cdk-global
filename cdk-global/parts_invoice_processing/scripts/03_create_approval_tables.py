"""Create or connect to a Lakebase Provisioned instance and set up the
invoice_approval_log table for HITL approval tracking.

This script:
1. Creates a Lakebase Provisioned instance (or reuses an existing one)
2. Generates an OAuth token for the database connection
3. Creates the invoice_approval_log table in PostgreSQL
"""

import os
import sys
import time
import uuid

import psycopg
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseInstance

INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "cdk-invoice-dev")
CAPACITY = os.environ.get("LAKEBASE_CAPACITY", "CU_1")
DATABASE_NAME = os.environ.get("LAKEBASE_DATABASE_NAME", "databricks_postgres")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS invoice_approval_log (
    approval_id       TEXT        PRIMARY KEY,
    invoice_id        TEXT        NOT NULL,
    invoice_number    TEXT,
    vendor_name       TEXT,
    invoice_total     NUMERIC(12, 2),
    match_status      TEXT,
    approval_route    TEXT        NOT NULL,
    assigned_to       TEXT,
    status            TEXT        NOT NULL DEFAULT 'PENDING',
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acted_on_at       TIMESTAMPTZ,
    acted_by          TEXT,
    rejection_reason  TEXT,
    escalated_from    TEXT,
    escalated_to      TEXT,
    slack_channel     TEXT,
    slack_thread_ts   TEXT,
    notes             TEXT
);

CREATE INDEX IF NOT EXISTS idx_approval_invoice_id ON invoice_approval_log (invoice_id);
CREATE INDEX IF NOT EXISTS idx_approval_status ON invoice_approval_log (status);
CREATE INDEX IF NOT EXISTS idx_approval_route_status ON invoice_approval_log (approval_route, status);
"""


def _wait_for_instance(w: WorkspaceClient, name: str, timeout: int = 600) -> None:
    """Poll until the Lakebase instance is AVAILABLE."""
    start = time.time()
    while time.time() - start < timeout:
        inst = w.database.get_database_instance(name=name)
        state = str(inst.state)
        if "AVAILABLE" in state:
            print(f"  Instance {name} is AVAILABLE")
            return
        print(f"  Instance {name} state: {state} — waiting …")
        time.sleep(15)
    raise TimeoutError(f"Instance {name} did not become AVAILABLE within {timeout}s")


def main():
    w = WorkspaceClient()
    username = w.current_user.me().user_name

    print(f"Ensuring Lakebase instance '{INSTANCE_NAME}' exists …")
    try:
        instance = w.database.get_database_instance(name=INSTANCE_NAME)
        print(f"  Found existing instance: {instance.name}")
    except Exception:
        print(f"  Creating new instance (capacity={CAPACITY}) …")
        instance = w.database.create_database_instance(
            DatabaseInstance(
                name=INSTANCE_NAME,
                capacity=CAPACITY,
            )
        )
        print(f"  Instance creation initiated: {instance.name}")

    _wait_for_instance(w, INSTANCE_NAME)
    instance = w.database.get_database_instance(name=INSTANCE_NAME)
    dns = instance.read_write_dns
    print(f"  DNS endpoint: {dns}")

    print("Generating database credential …")
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=[INSTANCE_NAME],
    )

    conn_str = f"host={dns} dbname={DATABASE_NAME} user={username} password={cred.token} sslmode=require"
    print(f"Connecting to {DATABASE_NAME}@{dns} …")
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()
            print(f"  Connected: {version[0][:60]}…")

            print("Creating invoice_approval_log table …")
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()

    print("Done — Lakebase instance and tables are ready.")
    print(f"\nConnection details for reference:")
    print(f"  Instance:  {INSTANCE_NAME}")
    print(f"  DNS:       {dns}")
    print(f"  Database:  {DATABASE_NAME}")


if __name__ == "__main__":
    main()
