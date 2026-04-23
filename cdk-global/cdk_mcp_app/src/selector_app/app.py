"""CDK MCP Tool Selector — Streamlit UI.

Browse APIs defined in api_config.yaml, select endpoints to deploy as
individual MCP tools, and deploy them to the MCP proxy app.
"""

import io
import json
import os
from pathlib import Path

import streamlit as st
import yaml
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import AppDeployment
from databricks.sdk.service.workspace import ImportFormat

MCP_PROXY_APP_NAME = os.environ.get("MCP_PROXY_APP_NAME", "mcp-proxy-dev-zach")
PROXY_SOURCE_PATH = os.environ.get(
    "MCP_PROXY_SOURCE_PATH",
    "/Workspace/Users/zachary.jacobson@cdk.com/.bundle/cdk-mcp-app/dev/files/src/mcp_proxy_app",
)
CONFIG_FILE = Path(__file__).parent / "api_config.yaml"


def get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient()


def get_current_user() -> dict:
    """Get the identity of the currently logged-in user via Databricks Apps SSO."""
    token = st.context.headers.get("x-forwarded-access-token")
    if not token:
        return {"display_name": "Local Dev", "email": "unknown"}
    try:
        user_client = WorkspaceClient(
            token=token,
            host=os.environ.get("DATABRICKS_HOST"),
        )
        me = user_client.current_user.me()
        return {"display_name": me.display_name, "email": me.user_name}
    except Exception:
        return {"display_name": "Unknown", "email": "unknown"}


def load_api_config() -> list[dict]:
    """Load API definitions from api_config.yaml."""
    if not CONFIG_FILE.exists():
        return []
    with open(CONFIG_FILE) as f:
        data = yaml.safe_load(f)
    return data.get("apis", [])


# ---------------------------------------------------------------------------
# Deploy helpers
# ---------------------------------------------------------------------------

def _read_existing_tools(w: WorkspaceClient, config_path: str) -> list[dict]:
    """Read the current deployed_tools.json from the workspace."""
    try:
        with w.workspace.download(config_path) as f:
            return json.loads(f.read())
    except Exception:
        return []


def _build_tool_definition(api: dict, endpoint: dict) -> dict:
    """Build a single tool definition from an API + endpoint pair."""
    tool_name = f"{api['name']}__{endpoint['name']}"

    parameters = []
    for p in endpoint.get("path_params", []):
        parameters.append({
            "name": p["name"],
            "type": p.get("type", "string"),
            "required": p.get("required", True),
            "in": "path",
            "description": p.get("description", ""),
        })
    for p in endpoint.get("query_params", []):
        param = {
            "name": p["name"],
            "type": p.get("type", "string"),
            "required": p.get("required", False),
            "in": "query",
            "description": p.get("description", ""),
        }
        if "default" in p:
            param["default"] = p["default"]
        parameters.append(param)

    body = None
    if endpoint.get("body"):
        body = {
            "content_type": endpoint["body"].get("content_type", "application/json"),
            "fields": [
                {
                    "name": f["name"],
                    "type": f.get("type", "string"),
                    "required": f.get("required", False),
                    "description": f.get("description", ""),
                }
                for f in endpoint["body"].get("fields", [])
            ],
        }

    tool_def = {
        "tool_name": tool_name,
        "description": endpoint.get("description", ""),
        "api_name": api["name"],
        "api_display_name": api.get("display_name", api["name"]),
        "base_url": api["base_url"],
        "method": endpoint["method"],
        "path": endpoint["path"],
        "auth": api.get("auth", {}),
        "parameters": parameters,
        "body": body,
    }

    if api.get("default_headers"):
        tool_def["default_headers"] = api["default_headers"]
    if endpoint.get("headers"):
        tool_def["headers"] = endpoint["headers"]

    return tool_def


def deploy_proxy_app(
    w: WorkspaceClient,
    tool_definitions: list[dict],
    app_name: str,
) -> dict:
    """Merge new tool definitions into deployed_tools.json and redeploy."""
    config_path = f"{PROXY_SOURCE_PATH}/deployed_tools.json"

    existing = _read_existing_tools(w, config_path)
    merged = {t["tool_name"]: t for t in existing}
    for tool in tool_definitions:
        merged[tool["tool_name"]] = tool
    all_tools = list(merged.values())

    config_content = json.dumps(all_tools, indent=2)
    w.workspace.upload(
        config_path,
        io.BytesIO(config_content.encode()),
        format=ImportFormat.AUTO,
        overwrite=True,
    )

    try:
        w.apps.get(app_name)
    except Exception:
        from databricks.sdk.service.apps import App
        w.apps.create_and_wait(App(name=app_name, description="CDK MCP Proxy Server"))

    deployment = w.apps.deploy_and_wait(
        app_name=app_name,
        app_deployment=AppDeployment(source_code_path=PROXY_SOURCE_PATH),
    )

    app_info = w.apps.get(app_name)
    return {
        "name": app_name,
        "url": getattr(app_info, "url", ""),
        "status": str(getattr(getattr(deployment, "status", None), "state", "DEPLOYED")),
    }


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def _render_endpoint_card(api: dict, endpoint: dict, key_prefix: str) -> bool:
    """Render a single endpoint as a selectable card. Returns True if selected."""
    method = endpoint["method"]
    method_colors = {
        "GET": "#61affe",
        "POST": "#49cc90",
        "PUT": "#fca130",
        "PATCH": "#50e3c2",
        "DELETE": "#f93e3e",
    }
    color = method_colors.get(method, "#999")

    with st.container(border=True):
        col_method, col_name = st.columns([1, 4])
        with col_method:
            st.markdown(
                f"<span style='background:{color};color:white;"
                f"padding:3px 10px;border-radius:4px;font-size:0.8em;"
                f"font-weight:700;font-family:monospace'>{method}</span>",
                unsafe_allow_html=True,
            )
        with col_name:
            st.markdown(f"**{endpoint['name']}**")

        st.caption(f"`{endpoint['path']}`")
        if endpoint.get("description"):
            st.caption(endpoint["description"])

        param_parts = []
        for p in endpoint.get("path_params", []):
            param_parts.append(f"`{p['name']}` (path, {'required' if p.get('required') else 'optional'})")
        for p in endpoint.get("query_params", []):
            param_parts.append(f"`{p['name']}` (query, {'required' if p.get('required') else 'optional'})")
        if endpoint.get("body"):
            field_names = [f["name"] for f in endpoint["body"].get("fields", [])]
            param_parts.append(f"body: {', '.join(field_names)}")
        if param_parts:
            st.caption("Params: " + " · ".join(param_parts))

        cb_key = f"{key_prefix}__{api['name']}__{endpoint['name']}"
        return st.checkbox("Select", key=cb_key, label_visibility="collapsed")


def _get_auth_env_vars(api: dict) -> list[str]:
    """Return the list of environment variable names needed for an API's auth."""
    auth = api.get("auth", {})
    method = auth.get("method", "none")
    env_vars = []
    if method in ("pat", "bearer"):
        if auth.get("credential_env"):
            env_vars.append(auth["credential_env"])
    elif method == "oauth":
        if auth.get("client_id_env"):
            env_vars.append(auth["client_id_env"])
        if auth.get("client_secret_env"):
            env_vars.append(auth["client_secret_env"])
    elif method == "basic":
        if auth.get("username_env"):
            env_vars.append(auth["username_env"])
        if auth.get("password_env"):
            env_vars.append(auth["password_env"])
    elif method == "api_key":
        if auth.get("credential_env"):
            env_vars.append(auth["credential_env"])
    return env_vars


def select_view(w: WorkspaceClient):
    """Main view: browse APIs and select endpoints to deploy as MCP tools."""
    st.markdown(
        "Browse available APIs and select endpoints to deploy as individual "
        "MCP tools on the proxy server."
    )

    apis = load_api_config()
    if not apis:
        st.warning("No APIs found. Add API definitions to `api_config.yaml`.")
        return

    search = st.text_input(
        "Search APIs",
        placeholder="e.g. github, posts, issues",
        label_visibility="collapsed",
    )

    filtered_apis = apis
    if search:
        q = search.lower()
        filtered_apis = [
            a for a in apis
            if q in a["name"].lower()
            or q in a.get("display_name", "").lower()
            or q in a.get("description", "").lower()
            or any(q in e["name"].lower() or q in e.get("description", "").lower()
                    for e in a.get("endpoints", []))
        ]

    if not filtered_apis:
        st.info("No APIs match your search.")
        return

    total_endpoints = sum(len(a.get("endpoints", [])) for a in apis)
    st.caption(
        f"Showing **{len(filtered_apis)}** API(s) with "
        f"**{sum(len(a.get('endpoints', [])) for a in filtered_apis)}** "
        f"endpoint(s) (of {total_endpoints} total)"
    )

    if "selected_endpoints" not in st.session_state:
        st.session_state.selected_endpoints = set()

    for api in filtered_apis:
        auth = api.get("auth", {})
        auth_method = auth.get("method", "none")
        auth_badge = auth_method.upper()
        auth_color = "#6c757d" if auth_method == "none" else "#17a2b8"
        endpoints = api.get("endpoints", [])

        with st.expander(
            f"**{api.get('display_name', api['name'])}** — "
            f"{len(endpoints)} endpoint(s)",
            expanded=False,
        ):
            col_info, col_auth = st.columns([3, 1])
            with col_info:
                st.caption(f"`{api['base_url']}`")
                if api.get("description"):
                    st.markdown(api["description"])
            with col_auth:
                st.markdown(
                    f"<span style='background:{auth_color};color:white;"
                    f"padding:2px 8px;border-radius:4px;font-size:0.75em;"
                    f"font-weight:600'>Auth: {auth_badge}</span>",
                    unsafe_allow_html=True,
                )

            env_vars = _get_auth_env_vars(api)
            if env_vars:
                st.info(
                    f"Required env var(s) on proxy app: `{'`, `'.join(env_vars)}`",
                    icon="🔑",
                )

            col_sel_all, _ = st.columns([1, 3])
            with col_sel_all:
                select_all_key = f"sel_all__{api['name']}"
                if st.checkbox("Select all endpoints", key=select_all_key):
                    for ep in endpoints:
                        st.session_state.selected_endpoints.add(
                            f"{api['name']}__{ep['name']}"
                        )

            for ep in endpoints:
                ep_key = f"{api['name']}__{ep['name']}"
                is_selected = _render_endpoint_card(api, ep, "ep")
                if is_selected:
                    st.session_state.selected_endpoints.add(ep_key)
                else:
                    st.session_state.selected_endpoints.discard(ep_key)

    # --- Deploy section ---
    st.markdown("---")
    st.subheader("Deploy Selected Tools")

    proxy_app_name = st.text_input(
        "Proxy app name",
        value=MCP_PROXY_APP_NAME,
        help="Name of the Databricks App that serves as the MCP proxy.",
    )

    selected = st.session_state.selected_endpoints
    selected_tools = []
    required_env_vars = set()

    for api in apis:
        for ep in api.get("endpoints", []):
            ep_key = f"{api['name']}__{ep['name']}"
            if ep_key in selected:
                selected_tools.append(_build_tool_definition(api, ep))
                for env_var in _get_auth_env_vars(api):
                    required_env_vars.add(env_var)

    if selected_tools:
        with st.expander(f"Review: {len(selected_tools)} tool(s) to deploy"):
            for tool in selected_tools:
                st.markdown(
                    f"- **{tool['tool_name']}** (`{tool['method']} {tool['path']}`) "
                    f"— {tool['description']}"
                )
            if required_env_vars:
                st.markdown("---")
                st.markdown(
                    "**Required environment variables** (set on the proxy app):"
                )
                for var in sorted(required_env_vars):
                    st.markdown(f"- `{var}`")

    deploy_btn = st.button(
        f"Deploy {len(selected_tools)} tool(s)",
        disabled=len(selected_tools) == 0,
        type="primary",
    )

    if deploy_btn:
        with st.status("Deploying...", expanded=True) as status:
            st.write(f"Deploying {len(selected_tools)} tool(s) to **{proxy_app_name}**...")
            try:
                result = deploy_proxy_app(w, selected_tools, proxy_app_name)
                st.success(f"Proxy app **{result['name']}** deployed!")
                if result.get("url"):
                    st.markdown(f"**App URL:** [{result['url']}]({result['url']})")
                    st.markdown(
                        f"**MCP endpoint:** `{result['url']}/mcp`"
                    )
            except Exception as e:
                st.error(f"Deployment failed: {e}")
                st.exception(e)

            status.update(label="Deployment complete!", state="complete")
            st.balloons()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def test_mcp_connection(w: WorkspaceClient):
    """Test the connection to the deployed MCP proxy server using OBO auth."""
    from databricks_ai_bridge import ModelServingUserCredentials
    from databricks_mcp import DatabricksMCPClient

    app_info = w.apps.get(MCP_PROXY_APP_NAME)
    mcp_server_url = f"{app_info.url}/mcp"

    user_client = WorkspaceClient(credentials_strategy=ModelServingUserCredentials())

    mcp_client = DatabricksMCPClient(
        server_url=mcp_server_url,
        workspace_client=user_client,
    )

    tools = mcp_client.list_tools()
    print(f"Available tools: {tools}")
    return tools


def main():
    st.set_page_config(
        page_title="CDK MCP Tool Selector",
        page_icon="🔌",
        layout="wide",
    )

    user = get_current_user()
    st.sidebar.markdown(f"Logged in as: **{user['display_name']}**")
    st.sidebar.caption(user["email"])

    st.title("CDK MCP Tool Selector")

    w = get_workspace_client()
    select_view(w)

    st.markdown("---")
    st.subheader("Test MCP Connection")
    if st.button("Test Connection", type="secondary"):
        with st.spinner("Connecting to MCP server..."):
            try:
                tools = test_mcp_connection(w)
                st.success(f"Connected! Found {len(tools)} tool(s).")
                for tool in tools:
                    st.write(f"- {tool}")
            except Exception as e:
                st.error(f"Connection failed: {e}")
                st.exception(e)


if __name__ == "__main__":
    main()
