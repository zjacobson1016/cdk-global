"""
CDK MCP Proxy Server

A FastMCP server that aggregates multiple upstream MCP servers into a single
unified MCP endpoint. Supports two server types:

  - **mcp** (default): Native MCP servers accessed via Databricks Unity Catalog
    external connections (JSON-RPC via /api/2.0/mcp/external/{name}).
  - **rest**: Plain REST API connections proxied via Unity Catalog connection
    proxy (/api/2.0/unity-catalog/connections/{name}/proxy/{path}).

Users select which servers to bundle via the companion Selector app,
which writes selected_servers.json before deploying this app.
"""

import json
import logging
import os
import uuid
from pathlib import Path

import httpx
from databricks.sdk import WorkspaceClient
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load selected server config (written by the Selector app at deploy time)
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "selected_servers.json"


def _load_selected_servers() -> list[dict]:
    if not CONFIG_PATH.exists():
        logger.warning("selected_servers.json not found — proxy has no upstream servers")
        return []
    with open(CONFIG_PATH) as f:
        return json.load(f)


SELECTED_SERVERS = _load_selected_servers()
SERVER_INDEX = {s["name"]: s for s in SELECTED_SERVERS}

logger.info(
    "MCP Proxy loaded %d upstream server(s): %s",
    len(SELECTED_SERVERS),
    [s["name"] for s in SELECTED_SERVERS],
)

# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "CDK MCP Proxy",
    instructions=(
        "You are the CDK MCP Proxy server. You aggregate tools from multiple "
        "upstream MCP servers and REST API connections into one endpoint.\n\n"
        "Use `list_servers` to see bundled servers.\n"
        "Use `list_upstream_tools` to discover tools on a specific server.\n"
        "Use `call_upstream_tool` to invoke any tool on any server."
    ),
)


def _get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient(
        client_id=os.environ.get("DATABRICKS_CLIENT_ID"),
        client_secret=os.environ.get("DATABRICKS_CLIENT_SECRET"),
    )


# ---------------------------------------------------------------------------
# MCP server helpers (JSON-RPC for native MCP connections)
# ---------------------------------------------------------------------------

def _call_upstream_mcp(
    w: WorkspaceClient,
    server: dict,
    method: str,
    params: dict | None = None,
) -> dict:
    """Send a JSON-RPC request to an upstream MCP server."""
    url = f"{w.config.host}/api/2.0/mcp/external/{server['name']}"
    headers = w.config.authenticate()
    headers["Content-Type"] = "application/json"

    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Error calling %s on %s: %s", method, server["name"], e)
        return {"error": str(e), "connection": server["name"]}


# ---------------------------------------------------------------------------
# REST connection proxy helpers (UC connections proxy endpoint)
# ---------------------------------------------------------------------------

def _get_connection_description(w: WorkspaceClient, connection_name: str) -> str:
    """Fetch the description/comment from a UC connection.

    The description can contain an API spec (swagger-style markdown) that
    tells the agent what endpoints, methods, and schemas are available.
    """
    try:
        conn = w.connections.get(connection_name)
        return conn.comment or ""
    except Exception as e:
        logger.warning("Could not fetch description for %s: %s", connection_name, e)
        return ""


def _call_rest_proxy(
    w: WorkspaceClient,
    connection_name: str,
    method: str,
    path: str,
    json_body: dict | str | None = None,
) -> str:
    """Call a REST API via the UC connections proxy endpoint."""
    url = (
        f"{w.config.host}/api/2.0/unity-catalog/connections/"
        f"{connection_name}/proxy/{path.lstrip('/')}"
    )
    headers = w.config.authenticate()
    headers["Content-Type"] = "application/json"
    headers["Accept-Encoding"] = "identity"

    body = None
    if json_body:
        body = json.loads(json_body) if isinstance(json_body, str) else json_body

    try:
        with httpx.Client(timeout=60) as client:
            resp = client.request(method.upper(), url, headers=headers, json=body)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": e.response.status_code, "message": e.response.text})
    except Exception as e:
        logger.error("REST proxy error for %s: %s", connection_name, e)
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_servers() -> str:
    """List all upstream MCP servers bundled in this proxy.

    Shows the server name and type for each server that was selected
    during deployment.
    """
    if not SELECTED_SERVERS:
        return "No upstream servers are configured. Redeploy via the Selector app."

    lines = ["# Bundled MCP Servers\n"]
    for s in SELECTED_SERVERS:
        stype = s.get("type", "mcp")
        host = s.get("host", "")
        if stype == "rest":
            base = s.get("base_path", "")
            lines.append(f"- **{s['name']}** (REST) — `{host}{base}`")
        else:
            lines.append(f"- **{s['name']}** (MCP) — `{host}`")
    lines.append(f"\n**{len(SELECTED_SERVERS)} server(s) available.**")
    lines.append(
        "\nUse `list_upstream_tools(server=\"<name>\")` to see available "
        "tools on a server."
    )
    return "\n".join(lines)


@mcp.tool()
def list_upstream_tools(server: str) -> str:
    """List all tools available on a specific upstream MCP server.

    Args:
        server: The server name (from `list_servers`).
    """
    if server not in SERVER_INDEX:
        available = ", ".join(sorted(SERVER_INDEX.keys()))
        return f"Unknown server: `{server}`.\n\nAvailable: {available}"

    server_entry = SERVER_INDEX[server]

    # REST connections: expose api_request tool with API spec from connection description
    if server_entry.get("type") == "rest":
        w = _get_workspace_client()
        conn_name = server_entry.get("connection_name", server_entry["name"])
        description = _get_connection_description(w, conn_name)

        lines = [
            f"# Tools on {server} (REST API proxy)\n",
            f"- **api_request**: Make HTTP requests to the `{conn_name}` API.\n"
            f"  Arguments: `method` (GET/POST/PUT/PATCH/DELETE), "
            f"`path` (API path), `json_body` (optional JSON body string or object)",
            f'\nExample: `call_upstream_tool(server="{server}", tool="api_request", '
            f'arguments={{"method": "GET", "path": "/your/endpoint"}})`',
        ]

        if description:
            lines.append("\n---\n")
            lines.append("## API Reference (from connection description)\n")
            lines.append(description)

        return "\n".join(lines)

    # MCP servers: standard tools/list via JSON-RPC
    w = _get_workspace_client()
    result = _call_upstream_mcp(w, server_entry, "tools/list")

    if "error" in result and "connection" in result:
        return f"Error listing tools on `{server}`: {result['error']}"

    tools = result.get("result", {}).get("tools", [])
    if not tools:
        return f"No tools found on `{server}`."

    lines = [f"# Tools on {server}\n"]
    for t in tools:
        name = t.get("name", "unknown")
        desc = t.get("description", "No description")
        lines.append(f"- **{name}**: {desc}")

    lines.append(f"\n**{len(tools)} tool(s).**")
    lines.append(
        f'\nUse `call_upstream_tool(server="{server}", tool="<tool_name>", '
        f'arguments={{...}})` to call one.'
    )
    return "\n".join(lines)


@mcp.tool()
def list_all_tools() -> str:
    """List tools from ALL bundled upstream MCP servers.

    Queries every configured server and returns a combined listing.
    """
    if not SELECTED_SERVERS:
        return "No upstream servers are configured."

    w = _get_workspace_client()
    lines = ["# All Upstream Tools\n"]
    total = 0

    for s in SELECTED_SERVERS:
        if s.get("type") == "rest":
            conn = s.get("connection_name", s["name"])
            description = _get_connection_description(w, conn)
            lines.append(f"\n## {s['name']} (REST API proxy)\n")
            lines.append(f"- **api_request**: Make HTTP requests to `{conn}`")
            if description:
                first_lines = "\n".join(description.splitlines()[:5])
                lines.append(f"\n  _{first_lines.strip()}_")
            total += 1
            continue

        result = _call_upstream_mcp(w, s, "tools/list")
        tools = result.get("result", {}).get("tools", [])
        if tools:
            lines.append(f"\n## {s['name']} ({len(tools)} tools)\n")
            for t in tools:
                lines.append(f"- **{t.get('name', '?')}**: {t.get('description', '')}")
            total += len(tools)
        elif "error" in result:
            lines.append(f"\n## {s['name']} — Error: {result.get('error', 'unknown')}\n")

    lines.append(f"\n**{total} total tool(s) across {len(SELECTED_SERVERS)} server(s).**")
    return "\n".join(lines)


@mcp.tool()
def call_upstream_tool(
    server: str,
    tool: str,
    arguments: dict | None = None,
) -> str:
    """Call a specific tool on an upstream MCP server.

    Use `list_upstream_tools` to discover available tools first.

    Args:
        server: The server name of the upstream MCP server.
        tool: The tool name to invoke.
        arguments: Tool arguments as a JSON object (varies by tool).
    """
    if server not in SERVER_INDEX:
        available = ", ".join(sorted(SERVER_INDEX.keys()))
        return f"Unknown server: `{server}`.\n\nAvailable: {available}"

    w = _get_workspace_client()
    server_entry = SERVER_INDEX[server]

    # REST connections: proxy via UC connections endpoint
    if server_entry.get("type") == "rest":
        args = arguments or {}
        conn_name = server_entry.get("connection_name", server_entry["name"])
        return _call_rest_proxy(
            w,
            conn_name,
            args.get("method", "GET"),
            args.get("path", "/"),
            args.get("json_body"),
        )

    # MCP servers: standard JSON-RPC tools/call
    call_params = {
        "name": tool,
        "arguments": arguments or {},
    }
    result = _call_upstream_mcp(w, server_entry, "tools/call", call_params)

    if "error" in result and "connection" in result:
        return f"Error calling `{tool}` on `{server}`: {result['error']}"

    rpc_result = result.get("result", {})

    content_list = rpc_result.get("content", [])
    if content_list:
        parts = []
        for item in content_list:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, dict):
                parts.append(json.dumps(item, indent=2))
            else:
                parts.append(str(item))
        return "\n".join(parts)

    return json.dumps(rpc_result, indent=2)


# ---------------------------------------------------------------------------
# ASGI app for uvicorn — Streamable HTTP on /mcp
# ---------------------------------------------------------------------------

app = mcp.http_app(path="/mcp", stateless_http=True)
