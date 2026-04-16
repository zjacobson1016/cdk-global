"""
CDK MCP Proxy Server

A FastMCP server that dynamically registers individual MCP tools from
API endpoint definitions. Each endpoint in deployed_tools.json becomes
its own MCP tool with a typed input schema.

The companion Selector app writes deployed_tools.json before deploying
this app.
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional

import httpx
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load tool config (written by the Selector app at deploy time)
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "deployed_tools.json"

TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": str,
    "object": str,
}


def _load_tool_configs() -> list[dict]:
    if not CONFIG_PATH.exists():
        logger.warning("deployed_tools.json not found — no tools to register")
        return []
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _resolve_auth_headers(auth_cfg: dict) -> dict[str, str]:
    """Build HTTP headers for the configured auth method."""
    method = auth_cfg.get("method", "none")

    if method == "none":
        return {}

    if method in ("pat", "bearer"):
        credential = os.environ.get(auth_cfg.get("credential_env", ""), "")
        if not credential:
            logger.warning(
                "Auth credential env var %s is not set",
                auth_cfg.get("credential_env"),
            )
            return {}
        header_name = auth_cfg.get("header_name", "Authorization")
        prefix = auth_cfg.get("header_prefix", "Bearer ")
        return {header_name: f"{prefix}{credential}"}

    if method == "basic":
        username = os.environ.get(auth_cfg.get("username_env", ""), "")
        password = os.environ.get(auth_cfg.get("password_env", ""), "")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    if method == "api_key":
        credential = os.environ.get(auth_cfg.get("credential_env", ""), "")
        header_name = auth_cfg.get("header_name", "X-API-Key")
        return {header_name: credential}

    if method == "oauth":
        return _resolve_oauth_headers(auth_cfg)

    return {}


def _resolve_oauth_headers(auth_cfg: dict) -> dict[str, str]:
    """Perform OAuth client_credentials flow and return Bearer header.

    Supports two credential patterns:
    - Inline: ``client_id`` / ``client_secret`` values directly in the config
    - Env-var: ``client_id_env`` / ``client_secret_env`` referencing env vars

    Credentials are sent via HTTP Basic auth (RFC 6749 §2.3.1).  If the
    ``token_url`` already contains query-string parameters (e.g.
    ``grant_type=client_credentials&scope=anonymous``), they are preserved
    and not duplicated in the POST body.
    """
    token_url = auth_cfg.get("token_url", "")

    client_id = auth_cfg.get("client_id") or os.environ.get(
        auth_cfg.get("client_id_env", ""), ""
    )
    client_secret = auth_cfg.get("client_secret") or os.environ.get(
        auth_cfg.get("client_secret_env", ""), ""
    )

    if not all([token_url, client_id, client_secret]):
        logger.warning("OAuth config incomplete — missing token_url or credentials")
        return {}

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                token_url,
                auth=(client_id, client_secret),
            )
            resp.raise_for_status()
            token = resp.json().get("access_token", "")
            header_name = auth_cfg.get("header_name", "Authorization")
            prefix = auth_cfg.get("header_prefix", "Bearer ")
            return {header_name: f"{prefix}{token}"}
    except Exception as e:
        logger.error("OAuth token exchange failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Request executor (shared by all generated tool handlers)
# ---------------------------------------------------------------------------

async def _execute_request(cfg: dict, kwargs: dict) -> str:
    """Execute an HTTP request based on tool config and caller-provided args."""
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    url = cfg["base_url"] + cfg["path"]
    for p in cfg.get("parameters", []):
        if p["in"] == "path" and p["name"] in kwargs:
            url = url.replace(f"{{{p['name']}}}", str(kwargs[p["name"]]))

    query_params = {}
    for p in cfg.get("parameters", []):
        if p["in"] == "query":
            val = kwargs.get(p["name"], p.get("default"))
            if val is not None:
                query_params[p["name"]] = val

    body = None
    if cfg.get("body") and cfg["body"].get("fields"):
        body = {
            f["name"]: kwargs[f["name"]]
            for f in cfg["body"]["fields"]
            if f["name"] in kwargs
        }
        if not body:
            body = None

    headers = _resolve_auth_headers(cfg.get("auth", {}))
    headers["Accept"] = "application/json"

    for dh in cfg.get("default_headers", []):
        param_name = dh["name"].replace("-", "_")
        val = kwargs.get(param_name, dh.get("default"))
        if val is not None:
            headers[dh["name"]] = str(val)

    for eh in cfg.get("headers", []):
        param_name = eh["name"].replace("-", "_")
        val = kwargs.get(param_name, eh.get("default"))
        if val is not None:
            headers[eh["name"]] = str(val)

    if body is not None:
        content_type = cfg.get("body", {}).get("content_type", "application/json")
        headers["Content-Type"] = content_type

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.request(
                cfg["method"],
                url,
                params=query_params or None,
                json=body,
                headers=headers,
            )
            resp.raise_for_status()
            try:
                return json.dumps(resp.json(), indent=2)
            except Exception:
                return resp.text
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "error": e.response.status_code,
            "message": e.response.text[:2000],
        })
    except Exception as e:
        logger.error("Request failed for %s: %s", cfg["tool_name"], e)
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Dynamic tool handler factory
# ---------------------------------------------------------------------------

_TYPE_NAMES = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "str",
    "object": "str",
}


def _build_handler(cfg: dict):
    """Create an async handler with real typed parameters via exec().

    FastMCP introspects function signatures with pydantic, so the handler
    must have actual named parameters — a **kwargs function with a patched
    __signature__ is not sufficient.
    """
    required_parts: list[str] = []
    optional_parts: list[str] = []
    all_param_names: list[str] = []

    for p in cfg.get("parameters", []):
        name = p["name"]
        type_str = _TYPE_NAMES.get(p.get("type", "string"), "str")
        all_param_names.append(name)

        if p.get("required", False):
            required_parts.append(f"{name}: {type_str}")
        elif "default" in p:
            required_parts.append(f"{name}: {type_str} = {repr(p['default'])}")
        else:
            optional_parts.append(f"{name}: Optional[{type_str}] = None")

    if cfg.get("body") and cfg["body"].get("fields"):
        for f in cfg["body"]["fields"]:
            name = f["name"]
            type_str = _TYPE_NAMES.get(f.get("type", "string"), "str")
            all_param_names.append(name)

            if f.get("required", False):
                required_parts.append(f"{name}: {type_str}")
            else:
                optional_parts.append(f"{name}: Optional[{type_str}] = None")

    for h in cfg.get("default_headers", []):
        name = h["name"].replace("-", "_")
        all_param_names.append(name)
        if h.get("default"):
            optional_parts.append(f"{name}: str = {repr(h['default'])}")
        elif h.get("required", False):
            required_parts.append(f"{name}: str")
        else:
            optional_parts.append(f"{name}: Optional[str] = None")

    for h in cfg.get("headers", []):
        name = h["name"].replace("-", "_")
        all_param_names.append(name)
        if h.get("required", False):
            required_parts.append(f"{name}: str")
        else:
            optional_parts.append(f"{name}: Optional[str] = None")

    params_str = ", ".join(required_parts + optional_parts)
    kwargs_items = ", ".join(f'"{n}": {n}' for n in all_param_names)
    func_name = cfg["tool_name"]
    docstring = cfg.get("description", "").replace("\\", "\\\\").replace('"', '\\"')

    code = (
        f"async def {func_name}({params_str}) -> str:\n"
        f'    """{docstring}"""\n'
        f"    return await _exec(_cfg, {{{kwargs_items}}})\n"
    )

    namespace = {
        "_exec": _execute_request,
        "_cfg": cfg,
        "Optional": Optional,
    }
    exec(code, namespace)  # noqa: S102
    return namespace[func_name]


# ---------------------------------------------------------------------------
# FastMCP Server + dynamic registration
# ---------------------------------------------------------------------------

TOOL_CONFIGS = _load_tool_configs()

mcp = FastMCP(
    "CDK MCP Proxy",
    instructions=(
        "You are the CDK MCP Proxy server. Each tool corresponds to a "
        "specific API endpoint. Call tools directly with the required "
        "parameters."
    ),
)

for _cfg in TOOL_CONFIGS:
    try:
        handler = _build_handler(_cfg)
        mcp.tool(name=_cfg["tool_name"], description=_cfg.get("description", ""))(handler)
        logger.info("Registered tool: %s", _cfg["tool_name"])
    except Exception as e:
        logger.error("Failed to register tool %s: %s", _cfg["tool_name"], e)

registered_count = sum(1 for _c in TOOL_CONFIGS if _c.get("tool_name"))
logger.info(
    "CDK MCP Proxy: %d tool config(s) processed",
    registered_count,
)

# ---------------------------------------------------------------------------
# ASGI app for uvicorn — Streamable HTTP on /mcp
# ---------------------------------------------------------------------------

app = mcp.http_app(path="/mcp", stateless_http=True)
