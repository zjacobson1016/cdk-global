"""Databricks Genie Space tool for natural language data exploration.

Uses the Databricks SDK Genie Conversation API to send natural language
questions to a curated Genie Space and return SQL-generated answers.
"""

import json
import logging
import os
from datetime import timedelta

from databricks.sdk import WorkspaceClient
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

GENIE_SPACE_ID = os.environ.get("GENIE_SPACE_ID", "01f12d1283e116888a546c7051d24358")


def _format_query_result(
    w: WorkspaceClient, message, space_id: str
) -> dict:
    """Extract SQL, description, and tabular data from a GenieMessage."""
    result = {
        "status": str(message.status) if message.status else "UNKNOWN",
        "sql": None,
        "description": None,
        "columns": [],
        "data": [],
        "row_count": 0,
        "text_response": None,
    }

    if message.error:
        result["error"] = str(message.error)
        return result

    if not message.attachments:
        return result

    for attachment in message.attachments:
        if attachment.text:
            result["text_response"] = attachment.text.content if hasattr(attachment.text, "content") else str(attachment.text)

        if attachment.query:
            result["sql"] = attachment.query.query
            result["description"] = attachment.query.description

            if attachment.attachment_id:
                try:
                    qr = w.genie.get_message_attachment_query_result(
                        space_id=space_id,
                        conversation_id=message.conversation_id,
                        message_id=message.message_id,
                        attachment_id=attachment.attachment_id,
                    )
                    if qr.statement_response and qr.statement_response.result:
                        sr = qr.statement_response
                        if sr.manifest and sr.manifest.schema and sr.manifest.schema.columns:
                            result["columns"] = [
                                c.name for c in sr.manifest.schema.columns
                            ]
                        if sr.result and sr.result.data_array:
                            result["data"] = sr.result.data_array
                            result["row_count"] = len(sr.result.data_array)
                except Exception as e:
                    logger.warning("Failed to fetch query result: %s", e)

    return result


@tool
def query_genie(question: str) -> str:
    """Ask a natural language question to the dealership Genie Space for
    data exploration. The Genie Space translates questions into SQL queries,
    executes them, and returns results. Use this for ad-hoc data questions
    about service history, revenue trends, parts usage, or any analytics
    that go beyond the pre-built tools.

    Args:
        question: A natural language question about dealership data
                  (e.g. "What were total service revenues last month?",
                  "Which service types generate the most revenue?")
    """
    space_id = GENIE_SPACE_ID
    if not space_id:
        return "ERROR: GENIE_SPACE_ID environment variable is not set. Cannot query Genie."

    try:
        # w = WorkspaceClient(
        #     client_id=os.environ.get("DATABRICKS_CLIENT_ID", ""),
        #     client_secret=os.environ.get("DATABRICKS_CLIENT_SECRET", ""),
        # )
        w = WorkspaceClient()
        wait_op = w.genie.start_conversation(
            space_id=space_id,
            content=question,
        )

        try:
            message = wait_op.result(timeout=timedelta(minutes=5))
        except Exception as wait_err:
            logger.warning("Genie wait returned non-COMPLETED status: %s", wait_err)
            try:
                message = w.genie.get_message(
                    space_id=space_id,
                    conversation_id=wait_op.conversation_id,
                    message_id=wait_op.message_id,
                )
            except Exception:
                return (
                    "Genie could not answer this question. "
                    "Try rephrasing with specific column or metric names. "
                    f"Details: {wait_err}"
                )

        result = _format_query_result(w, message, space_id)

        if result.get("error"):
            return (
                f"Genie could not generate an answer: {result['error']}. "
                "Try rephrasing the question."
            )

        if result.get("text_response") and not result.get("sql"):
            return f"Genie response: {result['text_response']}"

        parts = []
        if result.get("description"):
            parts.append(f"Description: {result['description']}")
        if result.get("sql"):
            parts.append(f"SQL: {result['sql']}")
        if result["columns"] and result["data"]:
            parts.append(f"Columns: {', '.join(result['columns'])}")
            rows_preview = result["data"][:50]
            parts.append(f"Results ({result['row_count']} rows):")
            parts.append(json.dumps(rows_preview, default=str))
        elif result.get("text_response"):
            parts.append(f"Response: {result['text_response']}")

        return "\n".join(parts) if parts else "Genie returned no results for this question."

    except Exception as e:
        logger.error("Genie query failed: %s", e)
        return f"ERROR: Genie query failed — {e}"
