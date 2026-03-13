"""Document Parsing Agent — ResponsesAgent wrapping ai_parse_document + ai_query.

Converts the SQL silver pipeline's two-step document parsing approach into a
parameterized Python agent:
  1. ai_parse_document(content) → extracted text  (via SQL Statement Execution)
  2. LLM structured extraction  → JSON fields     (via Foundation Model Serving API)

All parameters (model, prompt, response schema, temperature, etc.) are
configurable via constructor arguments or environment variables.
"""

import json
import logging
import os
import re
import time
from typing import Generator

import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
    output_to_responses_items_stream,
)

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from databricks.sdk.service.sql import StatementState
from langchain_core.messages import AIMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Default Configuration ────────────────────────────────────────────────────

DEFAULT_MODEL_ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"

DEFAULT_EXTRACTION_PROMPT = (
    "Extract structured invoice data from the following document text. "
    "Return all fields exactly as they appear in the document.\n\n"
    "{extracted_text}"
)

DEFAULT_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "invoice_extraction",
        "schema": {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "vendor_name": {"type": "string"},
                "vendor_address": {"type": "string"},
                "invoice_date": {"type": "string"},
                "due_date": {"type": "string"},
                "payment_terms": {"type": "string"},
                "po_reference": {"type": "string"},
                "bill_to_name": {"type": "string"},
                "bill_to_department": {"type": "string"},
                "part_number": {"type": "string"},
                "part_description": {"type": "string"},
                "quantity": {"type": "string"},
                "unit_price": {"type": "string"},
                "line_total": {"type": "string"},
                "subtotal": {"type": "string"},
                "tax": {"type": "string"},
                "total_amount": {"type": "string"},
            },
            "required": [
                "invoice_number", "vendor_name", "vendor_address",
                "invoice_date", "due_date", "payment_terms", "po_reference",
                "bill_to_name", "bill_to_department", "part_number",
                "part_description", "quantity", "unit_price", "line_total",
                "subtotal", "tax", "total_amount",
            ],
        },
        "strict": True,
    },
}

VOLUME_PATH_PATTERN = re.compile(r"/Volumes/[\w\-./]+")


# ─── Agent ────────────────────────────────────────────────────────────────────

class DocumentParsingAgent(ResponsesAgent):
    """Parameterized agent that parses documents and extracts structured fields.

    Constructor args fall back to environment variables, then to built-in defaults.
    This lets you swap the model, prompt, or schema without changing code — just
    set env vars on the serving endpoint or pass kwargs at log time.
    """

    def __init__(
        self,
        model_endpoint: str | None = None,
        extraction_prompt: str | None = None,
        response_schema: dict | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        warehouse_id: str | None = None,
        doc_parse_version: str = "2.0",
    ):
        self.model_endpoint = (
            model_endpoint
            or os.environ.get("MODEL_ENDPOINT", DEFAULT_MODEL_ENDPOINT)
        )
        self.extraction_prompt = (
            extraction_prompt
            or os.environ.get("EXTRACTION_PROMPT", DEFAULT_EXTRACTION_PROMPT)
        )
        self.response_schema = response_schema or DEFAULT_RESPONSE_SCHEMA
        self.temperature = (
            temperature if temperature is not None
            else float(os.environ.get("TEMPERATURE", "0.0"))
        )
        self.max_tokens = (
            max_tokens if max_tokens is not None
            else int(os.environ.get("MAX_TOKENS", "1024"))
        )
        self.warehouse_id = warehouse_id or os.environ.get("WAREHOUSE_ID", "")
        self.doc_parse_version = doc_parse_version
        self.w = WorkspaceClient()

    # ─── Step 1: Document Parsing (ai_parse_document equivalent) ──────────

    def parse_document(self, file_path: str) -> str:
        """Parse a document via ai_parse_document through SQL Statement Execution.

        Mirrors the SQL pipeline's approach:
            ai_parse_document(content, map('version', '2.0'))
        then concatenates all element text into a single string.

        Args:
            file_path: Unity Catalog Volume path,
                       e.g. /Volumes/catalog/schema/volume/invoice.pdf
        """
        if not self.warehouse_id:
            raise ValueError(
                "warehouse_id is required for ai_parse_document. "
                "Set WAREHOUSE_ID env var or pass warehouse_id to constructor."
            )

        sql = (
            "SELECT concat_ws('\\n', transform("
            "  CAST(ai_parse_document(content, map('version', "
            f"  '{self.doc_parse_version}')):document:elements "
            "  AS ARRAY<VARIANT>),"
            "  el -> el:content::STRING"
            ")) AS extracted_text "
            f"FROM read_files('{file_path}', format => 'binaryFile') "
            "LIMIT 1"
        )

        logger.info("Parsing document: %s", file_path)
        response = self.w.statement_execution.execute_statement(
            warehouse_id=self.warehouse_id,
            statement=sql,
            wait_timeout="120s",
        )

        while response.status and response.status.state in (
            StatementState.PENDING, StatementState.RUNNING,
        ):
            time.sleep(2)
            response = self.w.statement_execution.get_statement(
                response.statement_id,
            )

        if (
            response.status
            and response.status.state == StatementState.SUCCEEDED
            and response.result
            and response.result.data_array
        ):
            text = response.result.data_array[0][0] or ""
            logger.info("Extracted %d characters from document", len(text))
            return text

        error_msg = (
            response.status.error if response.status else "Unknown error"
        )
        raise RuntimeError(f"ai_parse_document failed: {error_msg}")

    # ─── Step 2: Structured Extraction (ai_query equivalent) ──────────────

    def extract_fields(self, extracted_text: str) -> str:
        """Extract structured fields from text via Foundation Model Serving API.

        Mirrors the SQL pipeline's ai_query call with responseFormat and
        modelParameters, using the Python SDK's serving_endpoints.query().

        Args:
            extracted_text: Plain text from a parsed document.

        Returns:
            JSON string matching the configured response_schema.
        """
        prompt = self.extraction_prompt.format(extracted_text=extracted_text)

        logger.info(
            "Extracting fields with %s (temp=%.1f, max_tokens=%d)",
            self.model_endpoint, self.temperature, self.max_tokens,
        )

        response = self.w.serving_endpoints.query(
            name=self.model_endpoint,
            messages=[
                ChatMessage(role=ChatMessageRole.USER, content=prompt),
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            extra_params={"response_format": self.response_schema},
        )

        content = response.choices[0].message.content
        usage = response.usage

        result_parts = [content]
        if usage:
            result_parts.append(
                f"\n---\n*Model: {self.model_endpoint} | "
                f"Tokens — prompt: {usage.prompt_tokens}, "
                f"completion: {usage.completion_tokens}, "
                f"total: {usage.total_tokens}*"
            )

        return "\n".join(result_parts)

    # ─── ResponsesAgent Interface ─────────────────────────────────────────

    def predict(
        self, request: ResponsesAgentRequest,
    ) -> ResponsesAgentResponse:
        outputs = [
            event.item
            for event in self.predict_stream(request)
            if event.type == "response.output_item.done"
        ]
        return ResponsesAgentResponse(output=outputs)

    def predict_stream(
        self, request: ResponsesAgentRequest,
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        user_message = self._last_user_message(request)

        if not user_message:
            yield from output_to_responses_items_stream(
                [AIMessage(content="No user message found.")]
            )
            return

        path_match = VOLUME_PATH_PATTERN.search(user_message)

        if path_match:
            file_path = path_match.group(0)
            yield from self._parse_and_extract(file_path)
        else:
            yield from self._extract_only(user_message)

    # ─── Internal Helpers ─────────────────────────────────────────────────

    def _last_user_message(self, request: ResponsesAgentRequest) -> str:
        for msg in reversed(request.input):
            msg_dict = msg.model_dump() if hasattr(msg, "model_dump") else msg
            if msg_dict.get("role") == "user":
                content = msg_dict.get("content", "")
                if isinstance(content, list):
                    return " ".join(
                        p.get("text", "")
                        for p in content
                        if p.get("type") == "input_text"
                    )
                return str(content)
        return ""

    def _parse_and_extract(self, file_path: str):
        """Full pipeline: parse document → extract structured fields."""
        yield from output_to_responses_items_stream(
            [AIMessage(content=f"[Step 1/2 — Parsing] Processing `{file_path}` with ai_parse_document...")]
        )

        try:
            extracted_text = self.parse_document(file_path)
        except Exception as e:
            logger.error("Document parsing failed: %s", e)
            yield from output_to_responses_items_stream(
                [AIMessage(content=f"Document parsing failed: {e}")]
            )
            return

        yield from output_to_responses_items_stream(
            [AIMessage(content=f"[Step 1/2 — Done] Extracted {len(extracted_text):,} characters.")]
        )

        yield from output_to_responses_items_stream(
            [AIMessage(content="[Step 2/2 — Extracting] Running structured extraction...")]
        )

        try:
            result = self.extract_fields(extracted_text)
        except Exception as e:
            logger.error("Field extraction failed: %s", e)
            yield from output_to_responses_items_stream(
                [AIMessage(content=f"Field extraction failed: {e}")]
            )
            return

        yield from output_to_responses_items_stream(
            [AIMessage(content=result)]
        )

    def _extract_only(self, raw_text: str):
        """Skip parsing — extract structured fields directly from supplied text."""
        yield from output_to_responses_items_stream(
            [AIMessage(content="[Extracting] No Volume path detected — treating input as raw text...")]
        )

        try:
            result = self.extract_fields(raw_text)
        except Exception as e:
            logger.error("Field extraction failed: %s", e)
            yield from output_to_responses_items_stream(
                [AIMessage(content=f"Field extraction failed: {e}")]
            )
            return

        yield from output_to_responses_items_stream(
            [AIMessage(content=result)]
        )


# ─── Module-level agent for MLflow ────────────────────────────────────────────

AGENT = DocumentParsingAgent()
mlflow.models.set_model(AGENT)
