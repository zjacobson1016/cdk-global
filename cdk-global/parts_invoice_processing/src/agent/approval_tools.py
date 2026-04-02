"""Custom LangChain tools for invoice approval write operations.

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

import re

import slack_notifier

logger = logging.getLogger(__name__)


def _parse_amount(value: str) -> float:
    """Strip currency formatting ($, commas) and return a plain float."""
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    return float(cleaned) if cleaned else 0.0

LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "cdk-invoice-dev")
LAKEBASE_DATABASE_NAME = os.environ.get("LAKEBASE_DATABASE_NAME", "databricks_postgres")

TOKEN_REFRESH_INTERVAL = 50 * 60  # 50 minutes (tokens expire at 60)

ESCALATION_CHAIN: dict[str, str] = {
    "SERVICE_MANAGER": "PARTS_DIRECTOR",
    "PARTS_DIRECTOR": "GENERAL_MANAGER",
    "GENERAL_MANAGER": "GENERAL_MANAGER",
    "EXCEPTION_REVIEW": "GENERAL_MANAGER",
    "RECEIVING_REVIEW": "PARTS_DIRECTOR",
}


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
def submit_for_approval(
    invoice_id: str,
    invoice_number: str,
    vendor_name: str,
    invoice_total: str,
    match_status: str,
    approval_route: str,
    classification: str,
    department: str = "",
) -> str:
    """Submit an invoice for human approval. Creates a PENDING entry in the
    approval log and sends a Slack notification to the appropriate approver
    channel. If the route is AUTO_APPROVED, logs it directly and notifies AP.

    Args:
        invoice_id: Invoice ID (e.g. INV-042)
        invoice_number: Invoice number from the parsed PDF
        vendor_name: Supplier / vendor name
        invoice_total: Total invoice amount as a string
        match_status: 3-way match result (MATCHED, PRICE_MISMATCH, etc.)
        approval_route: Determined route (SERVICE_MANAGER, PARTS_DIRECTOR, etc.)
        classification: Invoice classification (STANDARD, DISCREPANCY, etc.)
        department: Dealership department (Service, Body Shop, etc.)
    """
    approval_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    is_auto = approval_route == "AUTO_APPROVED"
    status = "AUTO_APPROVED" if is_auto else "PENDING"

    result = _execute_query(
        """INSERT INTO invoice_approval_log
             (approval_id, invoice_id, invoice_number, vendor_name, invoice_total,
              match_status, approval_route, assigned_to, status, submitted_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (approval_id, invoice_id, invoice_number, vendor_name, _parse_amount(invoice_total),
         match_status, approval_route, approval_route, status, now),
    )
    if not result["success"]:
        return f"ERROR: Failed to log approval request: {result['error']}"

    if is_auto:
        slack_notifier.send_auto_approved_notice(
            invoice_id, invoice_number, vendor_name, invoice_total
        )
        return (
            f"Invoice {invoice_id} has been AUTO-APPROVED. "
            f"Matched, under threshold. AP team notified via Slack."
        )

    thread_ts = slack_notifier.send_approval_request(
        invoice_id=invoice_id,
        invoice_number=invoice_number,
        vendor_name=vendor_name,
        invoice_total=invoice_total,
        match_status=match_status,
        approval_route=approval_route,
        classification=classification,
        department=department,
    )

    if thread_ts:
        channel = slack_notifier.APPROVAL_ROUTE_CHANNELS.get(approval_route, "")
        _execute_query(
            "UPDATE invoice_approval_log SET slack_thread_ts = %s, slack_channel = %s WHERE approval_id = %s",
            (thread_ts, channel, approval_id),
        )

    channel_name = slack_notifier.APPROVAL_ROUTE_CHANNELS.get(approval_route, "approver channel")
    return (
        f"Invoice {invoice_id} submitted for {approval_route} approval. "
        f"Status: PENDING. Slack notification sent to {channel_name}."
    )


@tool
def approve_invoice(invoice_id: str, approved_by: str, notes: str = "") -> str:
    """Approve a pending invoice. Updates the approval log and sends Slack confirmation.

    Args:
        invoice_id: Invoice ID to approve (e.g. INV-042)
        approved_by: Name or role of the person approving
        notes: Optional notes from the approver
    """
    pending = _execute_query(
        """SELECT approval_id, invoice_number, vendor_name, invoice_total,
                  approval_route, slack_thread_ts
           FROM invoice_approval_log
           WHERE invoice_id = %s AND status = 'PENDING'
           ORDER BY submitted_at DESC LIMIT 1""",
        (invoice_id,),
        fetch=True,
    )
    if not pending["success"] or not pending["rows"]:
        return f"No pending approval found for {invoice_id}. It may have already been processed."

    row = pending["rows"][0]
    now = datetime.now(timezone.utc)

    update = _execute_query(
        """UPDATE invoice_approval_log
           SET status = 'APPROVED', acted_on_at = %s, acted_by = %s, notes = %s
           WHERE approval_id = %s""",
        (now, approved_by, notes or None, row["approval_id"]),
    )
    if not update["success"]:
        return f"ERROR: Failed to update approval: {update['error']}"

    slack_notifier.send_approval_confirmation(
        invoice_id=invoice_id,
        invoice_number=row.get("invoice_number", ""),
        vendor_name=row.get("vendor_name", ""),
        invoice_total=row.get("invoice_total", "0"),
        acted_by=approved_by,
        action="APPROVED",
        thread_ts=row.get("slack_thread_ts"),
        approval_route=row.get("approval_route", ""),
    )

    return (
        f"Invoice {invoice_id} APPROVED by {approved_by}. "
        f"AP team notified via Slack."
    )


@tool
def reject_invoice(invoice_id: str, rejected_by: str, reason: str) -> str:
    """Reject a pending invoice with a reason. Updates the approval log and notifies AP.

    Args:
        invoice_id: Invoice ID to reject (e.g. INV-042)
        rejected_by: Name or role of the person rejecting
        reason: Reason for rejection (required)
    """
    pending = _execute_query(
        """SELECT approval_id, invoice_number, vendor_name, invoice_total,
                  approval_route, slack_thread_ts
           FROM invoice_approval_log
           WHERE invoice_id = %s AND status = 'PENDING'
           ORDER BY submitted_at DESC LIMIT 1""",
        (invoice_id,),
        fetch=True,
    )
    if not pending["success"] or not pending["rows"]:
        return f"No pending approval found for {invoice_id}. It may have already been processed."

    row = pending["rows"][0]
    now = datetime.now(timezone.utc)

    update = _execute_query(
        """UPDATE invoice_approval_log
           SET status = 'REJECTED', acted_on_at = %s, acted_by = %s, rejection_reason = %s
           WHERE approval_id = %s""",
        (now, rejected_by, reason, row["approval_id"]),
    )
    if not update["success"]:
        return f"ERROR: Failed to update rejection: {update['error']}"

    slack_notifier.send_approval_confirmation(
        invoice_id=invoice_id,
        invoice_number=row.get("invoice_number", ""),
        vendor_name=row.get("vendor_name", ""),
        invoice_total=row.get("invoice_total", "0"),
        acted_by=rejected_by,
        action="REJECTED",
        rejection_reason=reason,
        thread_ts=row.get("slack_thread_ts"),
        approval_route=row.get("approval_route", ""),
    )

    return (
        f"Invoice {invoice_id} REJECTED by {rejected_by}. "
        f"Reason: {reason}. AP team notified via Slack."
    )


@tool
def escalate_invoice(invoice_id: str, escalated_by: str) -> str:
    """Escalate a pending invoice to the next level in the approval chain.
    Marks the current entry as ESCALATED and creates a new PENDING entry
    for the next-level approver. Sends Slack notification to the new approver.

    Args:
        invoice_id: Invoice ID to escalate (e.g. INV-042)
        escalated_by: Name or role of the person escalating
    """
    pending = _execute_query(
        """SELECT approval_id, invoice_number, vendor_name, invoice_total,
                  match_status, approval_route, slack_thread_ts
           FROM invoice_approval_log
           WHERE invoice_id = %s AND status = 'PENDING'
           ORDER BY submitted_at DESC LIMIT 1""",
        (invoice_id,),
        fetch=True,
    )
    if not pending["success"] or not pending["rows"]:
        return f"No pending approval found for {invoice_id}. It may have already been processed."

    row = pending["rows"][0]
    current_route = row.get("approval_route", "")
    next_route = ESCALATION_CHAIN.get(current_route, "GENERAL_MANAGER")

    if next_route == current_route:
        return (
            f"Invoice {invoice_id} is already at the highest approval level "
            f"({current_route}). Cannot escalate further."
        )

    now = datetime.now(timezone.utc)

    _execute_query(
        """UPDATE invoice_approval_log
           SET status = 'ESCALATED', acted_on_at = %s, acted_by = %s, escalated_to = %s
           WHERE approval_id = %s""",
        (now, escalated_by, next_route, row["approval_id"]),
    )

    new_approval_id = str(uuid.uuid4())
    _execute_query(
        """INSERT INTO invoice_approval_log
             (approval_id, invoice_id, invoice_number, vendor_name, invoice_total,
              match_status, approval_route, assigned_to, status, submitted_at,
              escalated_from)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDING', %s, %s)""",
        (new_approval_id, invoice_id,
         row.get("invoice_number", ""), row.get("vendor_name", ""),
         row.get("invoice_total", "0"), row.get("match_status", ""),
         next_route, next_route, now, current_route),
    )

    new_thread_ts = slack_notifier.send_escalation_notice(
        invoice_id=invoice_id,
        invoice_number=row.get("invoice_number", ""),
        vendor_name=row.get("vendor_name", ""),
        invoice_total=row.get("invoice_total", "0"),
        escalated_from=current_route,
        escalated_to=next_route,
        thread_ts=row.get("slack_thread_ts"),
    )

    if new_thread_ts:
        channel = slack_notifier.APPROVAL_ROUTE_CHANNELS.get(next_route, "")
        _execute_query(
            "UPDATE invoice_approval_log SET slack_thread_ts = %s, slack_channel = %s WHERE approval_id = %s",
            (new_thread_ts, channel, new_approval_id),
        )

    return (
        f"Invoice {invoice_id} escalated from {current_route} to {next_route}. "
        f"New approver notified via Slack."
    )
