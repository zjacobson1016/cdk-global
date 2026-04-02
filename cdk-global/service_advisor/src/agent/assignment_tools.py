"""Custom LangChain tools for technician assignment write operations.

Uses Databricks Lakebase (managed PostgreSQL) via psycopg for low-latency
reads and writes. OAuth tokens are refreshed automatically before expiry.
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional



import psycopg
from databricks.sdk import WorkspaceClient
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "cdk-service-dev")
LAKEBASE_DATABASE_NAME = os.environ.get("LAKEBASE_DATABASE_NAME", "databricks_postgres")

TOKEN_REFRESH_INTERVAL = 50 * 60


class _LakebaseConnection:
    """Thread-safe Lakebase connection manager with automatic token refresh."""

    def __init__(self):
        self._lock = threading.Lock()
        self._dns: Optional[str] = None
        self._username: Optional[str] = None
        self._token: Optional[str] = None
        self._refresh_timer: Optional[threading.Timer] = None

    def _refresh_token(self) -> None:
        w = WorkspaceClient()
        cred = w.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[LAKEBASE_INSTANCE_NAME],
        )
        with self._lock:
            self._token = cred.token
        logger.info("Lakebase OAuth token refreshed")
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        if self._refresh_timer:
            self._refresh_timer.cancel()
        self._refresh_timer = threading.Timer(TOKEN_REFRESH_INTERVAL, self._refresh_token)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def _ensure_initialized(self) -> None:
        if self._dns is not None:
            return
        w = WorkspaceClient()
        instance = w.database.get_database_instance(name=LAKEBASE_INSTANCE_NAME)
        self._dns = instance.read_write_dns
        self._username = w.current_user.me().user_name
        self._refresh_token()

    @property
    def conn_string(self) -> str:
        self._ensure_initialized()
        with self._lock:
            token = self._token
        return (
            f"host={self._dns} "
            f"dbname={LAKEBASE_DATABASE_NAME} "
            f"user={self._username} "
            f"password={token} "
            f"sslmode=require"
        )


_lakebase = _LakebaseConnection()


def _execute_query(query: str, params: tuple = (), fetch: bool = False) -> dict:
    """Execute a PostgreSQL query against Lakebase and return results."""
    try:
        with psycopg.connect(_lakebase.conn_string) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = []
                if fetch and cur.description:
                    cols = [desc.name for desc in cur.description]
                    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
            conn.commit()
        return {"success": True, "rows": rows, "error": None}
    except Exception as e:
        logger.error("Lakebase query failed: %s", e)
        return {"success": False, "rows": [], "error": str(e)}


@tool
def assign_technician(
    appointment_id: str,
    customer_id: str,
    tech_id: str,
    reason: str = "",
) -> str:
    """Assign a technician to a customer's service appointment. Creates an entry
    in the assignment log so the service team knows who is handling which vehicle.

    Args:
        appointment_id: Appointment ID (e.g. APPT-00001)
        customer_id: Customer ID (e.g. CUST-0042)
        tech_id: Technician ID (e.g. TECH-003)
        reason: Reason for this assignment (e.g. "Best CSAT score for brake service")
    """
    existing = _execute_query(
        """SELECT assignment_id, tech_id
           FROM technician_assignments
           WHERE appointment_id = %s AND status = 'ASSIGNED'
           LIMIT 1""",
        (appointment_id,),
        fetch=True,
    )
    if existing["success"] and existing["rows"]:
        current_tech = existing["rows"][0]["tech_id"]
        return (
            f"Appointment {appointment_id} already has technician {current_tech} assigned. "
            f"Please reassign if needed."
        )

    assignment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    result = _execute_query(
        """INSERT INTO technician_assignments
             (assignment_id, appointment_id, customer_id, tech_id,
              assigned_at, assigned_by, reason, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'ASSIGNED')""",
        (assignment_id, appointment_id, customer_id, tech_id,
         now, "Service Advisor Agent", reason or None),
    )
    if not result["success"]:
        return f"ERROR: Failed to create assignment: {result['error']}"

    return (
        f"Technician {tech_id} has been assigned to appointment {appointment_id} "
        f"for customer {customer_id}. Assignment ID: {assignment_id}."
    )


@tool
def get_assignment_status(appointment_id: str) -> str:
    """Check if a technician has been assigned to a specific appointment.

    Args:
        appointment_id: Appointment ID to check (e.g. APPT-00001)
    """
    result = _execute_query(
        """SELECT assignment_id, tech_id, assigned_at, assigned_by, reason, status
           FROM technician_assignments
           WHERE appointment_id = %s
           ORDER BY assigned_at DESC
           LIMIT 1""",
        (appointment_id,),
        fetch=True,
    )
    if not result["success"]:
        return f"ERROR: Failed to check assignment: {result['error']}"

    if not result["rows"]:
        return f"No technician has been assigned to appointment {appointment_id} yet."

    row = result["rows"][0]
    return (
        f"Appointment {appointment_id} — Technician {row['tech_id']} assigned "
        f"at {row['assigned_at']} by {row['assigned_by']}. "
        f"Status: {row['status']}. Reason: {row.get('reason', 'N/A')}."
    )
