"""Register Unity Catalog functions for the Invoice Processing Agent (Genie variant).

All 5 gold_invoice_match_sync query functions (get_invoice_details,
search_invoices_by_supplier, get_invoices_by_route, get_supplier_performance,
get_invoice_summary) are backed by the Invoice Approval Management Genie Space
while keeping the exact same function names and parameter signatures so the
agent does not need rebuilding.

Approval workflow functions and agent endpoint query are unchanged.
"""
from databricks.connect import DatabricksSession

CATALOG = "mfg_mc_se_sa"
SCHEMA = "cdk"
GENIE_SPACE_ID = "01f115d7a668194eba3e8bcf9297cc05"
WORKSPACE_HOST = "https://fevm-mfg-mc-se-sa.cloud.databricks.com"
SECRET_SCOPE = "cdk-invoicing"
SECRET_KEY = "databricks-token"

spark = DatabricksSession.builder.profile("group-demo").serverless().getOrCreate()


# ═════════════════════════════════════════════════════════════════════════════
# GENIE SPACE FUNCTION (replaces 5 individual gold_invoice_match_sync queries)
# ═════════════════════════════════════════════════════════════════════════════

# ── Tool 1a: Internal Python UDF (accepts credentials as parameters) ────────
GENIE_IMPL_BODY = (
    "import json, time, urllib.request, urllib.error\n"
    "\n"
    'SPACE_ID = "' + GENIE_SPACE_ID + '"\n'
    """
host = db_host.rstrip("/")
if not host.startswith("https://"):
    host = f"https://{host}"

headers = {"Authorization": f"Bearer {db_token}", "Content-Type": "application/json"}

def _api(method, path, body=None):
    url = f"{host}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

resp = _api("POST", f"/api/2.0/genie/spaces/{SPACE_ID}/start-conversation", {"content": question})
conversation_id = resp["conversation_id"]
message_id = resp["message_id"]

status = None
msg = {}
for _ in range(60):
    msg = _api("GET", f"/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conversation_id}/messages/{message_id}")
    status = msg.get("status")
    if status in ("COMPLETED", "FAILED", "CANCELLED"):
        break
    time.sleep(2)

if status != "COMPLETED":
    return json.dumps({"error": f"Genie query {status}", "question": question})

attachments = msg.get("attachments", [])
for att in attachments:
    query_info = att.get("query")
    if query_info:
        att_id = att.get("attachment_id", att.get("id"))
        result = _api("GET", f"/api/2.0/genie/spaces/{SPACE_ID}/conversations/{conversation_id}/messages/{message_id}/query-result/{att_id}")
        manifest = result.get("statement_response", {}).get("manifest", {})
        columns = [c["name"] for c in manifest.get("schema", {}).get("columns", [])]
        data_array = result.get("statement_response", {}).get("result", {}).get("data_array", [])
        return json.dumps({
            "sql": query_info.get("query", ""),
            "description": query_info.get("description", ""),
            "columns": columns,
            "data": data_array[:50],
            "row_count": len(data_array)
        })
    text_info = att.get("text")
    if text_info:
        return text_info.get("content", "No content")

return json.dumps({"error": "No results returned", "question": question})
"""
)

spark.sql(
    f"CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}._ask_invoice_genie_impl("
    "question STRING, db_host STRING, db_token STRING) "
    "RETURNS STRING "
    "LANGUAGE PYTHON "
    "COMMENT 'Internal implementation for Genie Space queries. "
    "Use ask_invoice_genie() instead — it injects credentials automatically.' "
    "AS $$"
    + GENIE_IMPL_BODY
    + "$$"
)
print("1a/10 _ask_invoice_genie_impl")


# ── Tool 1b: Public SQL wrapper (injects credentials via SECRET) ────────────
spark.sql(f"DROP FUNCTION IF EXISTS {CATALOG}.{SCHEMA}.ask_invoice_genie")
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.ask_invoice_genie(question STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Ask a natural-language question about invoices to the Invoice Approval Management Genie Space. Handles invoice lookups, supplier searches, approval routing, supplier performance, and invoice summaries through natural language. Returns JSON with the generated SQL, columns, data rows, and row count. Use this for any ad-hoc invoice or match data question.'
RETURN
  SELECT {CATALOG}.{SCHEMA}._ask_invoice_genie_impl(
    question,
    '{WORKSPACE_HOST}',
    SECRET('{SECRET_SCOPE}', '{SECRET_KEY}')
  )
""")
print("1b/10 ask_invoice_genie")


# ═════════════════════════════════════════════════════════════════════════════
# GENIE-BACKED INVOICE QUERY FUNCTIONS (exact same names as create_functions.py)
# ═════════════════════════════════════════════════════════════════════════════

# ── Tool 2: Get invoice details ─────────────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_invoice_details(invoice_number_input STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Look up detailed invoice information including 3-way match status, approval routing, and classification. Use this when the user asks about a specific invoice by invoice number or ID.'
RETURN
  SELECT {CATALOG}.{SCHEMA}.ask_invoice_genie(
    CONCAT('Get all details for invoice with number or ID ', invoice_number_input,
    '. Include invoice ID, invoice number, vendor name, invoice date, due date, ',
    'invoice total, PO number, part number, part description, quantity, unit price, ',
    'match status, price variance percentage, quantity variance, approval route, ',
    'invoice classification, vendor tier, department, and whether received via email. ',
    'Only show invoices that have not been approved yet.')
  )
""")
print("2/10 get_invoice_details")


# ── Tool 3: Search invoices by supplier ─────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.search_invoices_by_supplier(supplier_name_input STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Search for invoices from a specific supplier. Accepts partial supplier name matches. Returns invoice details with match status and approval routing.'
RETURN
  SELECT {CATALOG}.{SCHEMA}.ask_invoice_genie(
    CONCAT('Search for invoices from supplier matching "', supplier_name_input,
    '". Show invoice ID, invoice number, vendor name, invoice total, match status, ',
    'approval route, invoice classification, and vendor tier. ',
    'Order by invoice total descending, limit 20. Only show invoices not yet approved.')
  )
""")
print("3/10 search_invoices_by_supplier")


# ── Tool 4: Get invoices by approval route ──────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_invoices_by_route(approval_route_input STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Get invoices assigned to a given approval route. Valid routes: AUTO_APPROVED, SERVICE_MANAGER, PARTS_DIRECTOR, GENERAL_MANAGER, EXCEPTION_REVIEW, RECEIVING_REVIEW, PO_REQUIRED. Pass "ALL" to see all non-auto-approved invoices.'
RETURN
  SELECT {CATALOG}.{SCHEMA}.ask_invoice_genie(
    CONCAT('Get invoices assigned to approval route ', approval_route_input,
    '. Exclude auto-approved invoices. Show invoice ID, invoice number, vendor name, ',
    'invoice total, match status, approval route, invoice classification, vendor tier, ',
    'and department. Order by invoice total descending, limit 25. ',
    'Only show invoices that have not been approved yet.')
  )
""")
print("4/10 get_invoices_by_route")


# ── Tool 5: Get supplier performance summary ────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_supplier_performance(supplier_name_input STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Get supplier performance metrics including match rate, total invoice value, and pricing accuracy. Useful for evaluating vendor reliability.'
RETURN
  SELECT {CATALOG}.{SCHEMA}.ask_invoice_genie(
    CONCAT('Get supplier performance metrics for suppliers matching "', supplier_name_input,
    '". Show vendor name, vendor tier, total invoices, matched invoices count, ',
    'discrepancy invoices count, match rate percentage, total invoice value, ',
    'average invoice value, and average price variance percentage. ',
    'Only include invoices that have not been approved yet.')
  )
""")
print("5/10 get_supplier_performance")


# ── Tool 6: Get invoice processing summary ──────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_invoice_summary()
RETURNS STRING
LANGUAGE SQL
COMMENT 'Get an overall summary of invoice processing metrics grouped by match status, approval route, and classification. Use this for high-level reporting and status overview.'
RETURN
  SELECT {CATALOG}.{SCHEMA}.ask_invoice_genie(
    'Get overall summary of invoice processing metrics grouped by match status, '
    || 'approval route, and invoice classification. Show invoice count, total value, '
    || 'and average invoice value for each group. Order by invoice count descending. '
    || 'Only include invoices that have not been approved yet.'
  )
""")
print("6/10 get_invoice_summary")


# ═════════════════════════════════════════════════════════════════════════════
# APPROVAL WORKFLOW READ FUNCTIONS (query invoice_approval_log via Lakebase)
# ═════════════════════════════════════════════════════════════════════════════

# ── Tool 7: Get approval status for a specific invoice ──────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_approval_status(invoice_id_input STRING)
RETURNS TABLE(
  approval_id STRING,
  invoice_id STRING,
  invoice_number STRING,
  vendor_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  assigned_to STRING,
  status STRING,
  submitted_at TIMESTAMP,
  acted_on_at TIMESTAMP,
  acted_by STRING,
  rejection_reason STRING,
  escalated_to STRING,
  notes STRING
)
LANGUAGE SQL
COMMENT 'Get the full approval history for a specific invoice. Shows all approval actions (submissions, approvals, rejections, escalations) in chronological order. Use when the user asks about the status of an invoice approval.'
RETURN
  SELECT
    approval_id,
    invoice_id,
    invoice_number,
    vendor_name,
    invoice_total,
    match_status,
    approval_route,
    assigned_to,
    status,
    submitted_at,
    acted_on_at,
    acted_by,
    rejection_reason,
    escalated_to,
    notes
  FROM cdk_invoicing.public.invoice_approval_log
  WHERE invoice_id = invoice_id_input
     OR invoice_number = invoice_id_input
  ORDER BY submitted_at DESC
""")
print("7/10 get_approval_status")


# ── Tool 8: Get pending approvals for a given route/role ────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_pending_approvals_for_route(approval_route_input STRING)
RETURNS TABLE(
  approval_id STRING,
  invoice_id STRING,
  invoice_number STRING,
  vendor_name STRING,
  invoice_total DECIMAL(12,2),
  match_status STRING,
  approval_route STRING,
  submitted_at TIMESTAMP,
  hours_pending DOUBLE
)
LANGUAGE SQL
COMMENT 'Get all invoices with PENDING approval status for a given route. Use when an approver asks "what do I need to approve?" Valid routes: SERVICE_MANAGER, PARTS_DIRECTOR, GENERAL_MANAGER, EXCEPTION_REVIEW, RECEIVING_REVIEW. Pass "ALL" for all pending.'
RETURN
  SELECT
    approval_id,
    invoice_id,
    invoice_number,
    vendor_name,
    invoice_total,
    match_status,
    approval_route,
    submitted_at,
    ROUND((unix_timestamp(current_timestamp()) - unix_timestamp(submitted_at)) / 3600.0, 1) AS hours_pending
  FROM cdk_invoicing.public.invoice_approval_log
  WHERE status = 'PENDING'
    AND (
      approval_route = UPPER(approval_route_input)
      OR UPPER(approval_route_input) = 'ALL'
    )
  ORDER BY submitted_at ASC
  LIMIT 25
""")
print("8/10 get_pending_approvals_for_route")


# ── Tool 9: Approval pipeline summary ──────────────────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.get_approval_summary()
RETURNS TABLE(
  status STRING,
  approval_route STRING,
  request_count BIGINT,
  total_value DOUBLE,
  avg_hours_pending DOUBLE,
  oldest_request TIMESTAMP
)
LANGUAGE SQL
COMMENT 'Aggregate statistics on the approval pipeline: counts by status and route, total value, and average wait time. Use for operational dashboards and identifying bottlenecks.'
RETURN
  SELECT
    status,
    approval_route,
    COUNT(*) AS request_count,
    CAST(SUM(invoice_total) AS DOUBLE) AS total_value,
    ROUND(AVG(
      CASE WHEN status = 'PENDING'
        THEN (unix_timestamp(current_timestamp()) - unix_timestamp(submitted_at)) / 3600.0
        ELSE (unix_timestamp(acted_on_at) - unix_timestamp(submitted_at)) / 3600.0
      END
    ), 1) AS avg_hours_pending,
    MIN(submitted_at) AS oldest_request
  FROM cdk_invoicing.public.invoice_approval_log
  GROUP BY status, approval_route
  ORDER BY
    CASE status WHEN 'PENDING' THEN 1 WHEN 'ESCALATED' THEN 2 ELSE 3 END,
    request_count DESC
""")
print("9/10 get_approval_summary")


# ═════════════════════════════════════════════════════════════════════════════
# AGENT ENDPOINT QUERY FUNCTION
# ═════════════════════════════════════════════════════════════════════════════

# ── Tool 10: Query the parts invoice agent endpoint ──────────────────────────
spark.sql(f"""
CREATE OR REPLACE FUNCTION {CATALOG}.{SCHEMA}.ask_parts_invoice_agent(question STRING)
RETURNS STRING
LANGUAGE SQL
COMMENT 'Ask a natural-language question to the Parts Invoice Processing Agent. The agent can look up invoices, check approval status, search by supplier, and more. Returns the agent response as a string.'
RETURN
  SELECT ai_query(
    'agents_mfg_mc_se_sa-cdk-parts_invoice_agent', question
    ) AS response
""")
print("10/10 ask_parts_invoice_agent")

print(f"\nAll 10 UC functions created in {CATALOG}.{SCHEMA}")
