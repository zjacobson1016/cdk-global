"""Slack notification utility for the invoice approval workflow.

Sends structured messages to Slack channels when invoices are submitted,
approved, rejected, or escalated. Uses the slack_sdk WebClient with a
bot token from the SLACK_BOT_TOKEN environment variable.

Channel mapping is configured via APPROVAL_ROUTE_CHANNELS. Set the
AP_CHANNEL for accounts-payable confirmations.
"""

import logging
import os
import ssl
from typing import Optional

import certifi
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)
#Read slack token in from image file

AP_CHANNEL = os.environ.get("SLACK_AP_CHANNEL", "#ap-invoices")

APPROVAL_ROUTE_CHANNELS: dict[str, str] = {
    "SERVICE_MANAGER": os.environ.get("SLACK_CH_SERVICE_MGR", "#service-approvals"),
    "PARTS_DIRECTOR": os.environ.get("SLACK_CH_PARTS_DIR", "#parts-approvals"),
    "GENERAL_MANAGER": os.environ.get("SLACK_CH_GENERAL_MGR", "#gm-approvals"),
    "EXCEPTION_REVIEW": os.environ.get("SLACK_CH_EXCEPTION", "#exception-review"),
    "RECEIVING_REVIEW": os.environ.get("SLACK_CH_RECEIVING", "#receiving-review"),
    "PO_REQUIRED": os.environ.get("SLACK_CH_EXCEPTION", "#exception-review"),
}

ESCALATION_CHAIN: dict[str, str] = {
    "SERVICE_MANAGER": "PARTS_DIRECTOR",
    "PARTS_DIRECTOR": "GENERAL_MANAGER",
    "GENERAL_MANAGER": "GENERAL_MANAGER",
    "EXCEPTION_REVIEW": "GENERAL_MANAGER",
    "RECEIVING_REVIEW": "PARTS_DIRECTOR",
}


def _get_client() -> Optional[WebClient]:
    if not SLACK_BOT_TOKEN:
        logger.warning("SLACK_BOT_TOKEN not set – Slack notifications disabled")
        return None
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    return WebClient(token=SLACK_BOT_TOKEN, ssl=ssl_context)


def _fmt_currency(amount) -> str:
    try:
        return f"${float(amount):,.2f}"
    except (TypeError, ValueError):
        return str(amount)


def send_approval_request(
    invoice_id: str,
    invoice_number: str,
    vendor_name: str,
    invoice_total,
    match_status: str,
    approval_route: str,
    classification: str,
    department: str = "",
) -> Optional[str]:
    """Post a new approval request to the appropriate approver channel.

    Returns the Slack thread timestamp (thread_ts) so replies can be tracked,
    or None if the message could not be sent.
    """
    client = _get_client()
    if client is None:
        return None

    channel = APPROVAL_ROUTE_CHANNELS.get(approval_route, AP_CHANNEL)
    total_str = _fmt_currency(invoice_total)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Invoice Approval Required – {invoice_id}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Invoice #:*\n{invoice_number}"},
                {"type": "mrkdwn", "text": f"*Vendor:*\n{vendor_name}"},
                {"type": "mrkdwn", "text": f"*Amount:*\n{total_str}"},
                {"type": "mrkdwn", "text": f"*Match Status:*\n{match_status}"},
                {"type": "mrkdwn", "text": f"*Classification:*\n{classification}"},
                {"type": "mrkdwn", "text": f"*Department:*\n{department or 'N/A'}"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Assigned to:* {approval_route}\n\n"
                    "Reply in this thread to take action:\n"
                    f"• `approve {invoice_id}` — approve this invoice\n"
                    f"• `reject {invoice_id} <reason>` — reject with reason\n"
                    f"• `escalate {invoice_id}` — escalate to next level"
                ),
            },
        },
    ]

    try:
        resp = client.chat_postMessage(
            channel=channel,
            text=f"Approval required for {invoice_id} ({total_str}) from {vendor_name}",
            blocks=blocks,
        )
        logger.info("Approval request posted to %s for %s", channel, invoice_id)
        return resp["ts"]
    except SlackApiError as e:
        logger.error("Failed to post approval request: %s", e.response["error"])
        return None


def send_approval_confirmation(
    invoice_id: str,
    invoice_number: str,
    vendor_name: str,
    invoice_total,
    acted_by: str,
    action: str,
    rejection_reason: str = "",
    thread_ts: Optional[str] = None,
    approval_route: str = "",
) -> None:
    """Notify the AP channel and reply in the original approval thread."""
    client = _get_client()
    if client is None:
        return

    total_str = _fmt_currency(invoice_total)
    emoji = ":white_check_mark:" if action == "APPROVED" else ":x:"
    reason_line = f"\n*Reason:* {rejection_reason}" if rejection_reason else ""

    ap_text = (
        f"{emoji} *Invoice {invoice_id} {action}*\n"
        f"*Invoice #:* {invoice_number}  |  *Vendor:* {vendor_name}  |  *Amount:* {total_str}\n"
        f"*By:* {acted_by}{reason_line}"
    )

    try:
        client.chat_postMessage(channel=AP_CHANNEL, text=ap_text)
    except SlackApiError as e:
        logger.error("Failed to post AP confirmation: %s", e.response["error"])

    if thread_ts and approval_route:
        channel = APPROVAL_ROUTE_CHANNELS.get(approval_route, AP_CHANNEL)
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"{emoji} {action} by {acted_by}.{reason_line}",
            )
        except SlackApiError as e:
            logger.error("Failed to reply in approval thread: %s", e.response["error"])


def send_escalation_notice(
    invoice_id: str,
    invoice_number: str,
    vendor_name: str,
    invoice_total,
    escalated_from: str,
    escalated_to: str,
    thread_ts: Optional[str] = None,
) -> Optional[str]:
    """Notify the next-level approver channel about an escalation.

    Returns the new thread_ts from the escalation channel.
    """
    client = _get_client()
    if client is None:
        return None

    channel = APPROVAL_ROUTE_CHANNELS.get(escalated_to, AP_CHANNEL)
    total_str = _fmt_currency(invoice_total)

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Escalated Invoice – {invoice_id}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Invoice #:*\n{invoice_number}"},
                {"type": "mrkdwn", "text": f"*Vendor:*\n{vendor_name}"},
                {"type": "mrkdwn", "text": f"*Amount:*\n{total_str}"},
                {"type": "mrkdwn", "text": f"*Escalated from:*\n{escalated_from}"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"This invoice was escalated from *{escalated_from}* and requires your review.\n\n"
                    "Reply in this thread:\n"
                    f"• `approve {invoice_id}`\n"
                    f"• `reject {invoice_id} <reason>`\n"
                    f"• `escalate {invoice_id}`"
                ),
            },
        },
    ]

    try:
        resp = client.chat_postMessage(
            channel=channel,
            text=f"Escalated: {invoice_id} ({total_str}) from {vendor_name}",
            blocks=blocks,
        )
        new_ts = resp["ts"]
    except SlackApiError as e:
        logger.error("Failed to post escalation notice: %s", e.response["error"])
        return None

    if thread_ts:
        old_channel = APPROVAL_ROUTE_CHANNELS.get(escalated_from, AP_CHANNEL)
        try:
            client.chat_postMessage(
                channel=old_channel,
                thread_ts=thread_ts,
                text=f":arrow_up: Escalated to *{escalated_to}*.",
            )
        except SlackApiError as e:
            logger.error("Failed to reply in original thread: %s", e.response["error"])

    return new_ts


def send_auto_approved_notice(
    invoice_id: str,
    invoice_number: str,
    vendor_name: str,
    invoice_total,
) -> None:
    """Notify the AP channel that an invoice was auto-approved."""
    client = _get_client()
    if client is None:
        return

    total_str = _fmt_currency(invoice_total)
    text = (
        f":white_check_mark: *Invoice {invoice_id} AUTO-APPROVED*\n"
        f"*Invoice #:* {invoice_number}  |  *Vendor:* {vendor_name}  |  *Amount:* {total_str}\n"
        "No manual approval needed — matched, under threshold, preferred vendor."
    )
    try:
        client.chat_postMessage(channel=AP_CHANNEL, text=text)
    except SlackApiError as e:
        logger.error("Failed to post auto-approval notice: %s", e.response["error"])
