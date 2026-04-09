"""MCP Server Registry — Streamlit UI.

Browse ALL HTTP connections (MCP servers and REST APIs) in one unified view.
MCP servers are deployed via the bundled MCP proxy app. REST API connections
are proxied via Unity Catalog connection proxy endpoints.
"""

import io
import json
import os

import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config
from databricks.sdk.service.apps import AppDeployment
from databricks.sdk.service.catalog import ConnectionType
from databricks.sdk.service.workspace import ImportFormat

MCP_PROXY_APP_NAME = os.environ.get("MCP_PROXY_APP_NAME", "mcp-proxy-dev")
PROXY_SOURCE_PATH = os.environ.get(
    "MCP_PROXY_SOURCE_PATH",
    "/Workspace/Users/zach.jacobson@databricks.com/.bundle/cdk-mcp-app/dev/files/src/mcp_proxy_app",
)

AUTH_TYPE_OPTIONS = [
    "Bearer Token",
    "OAuth Machine to Machine",
    "OAuth User to Machine Shared",
    "OAuth User to Machine Per User",
]

AUTH_TYPE_KEYS = {
    "Bearer Token": "bearer",
    "OAuth Machine to Machine": "oauth_m2m",
    "OAuth User to Machine Shared": "oauth_u2m_shared",
    "OAuth User to Machine Per User": "oauth_u2m_per_user",
}

OAUTH_PROVIDERS = [
    "Manual configuration",
]

CREDENTIAL_EXCHANGE_METHODS = {
    "header_and_body": "Header & Body (default)",
    "body_only": "Body Only",
    "header_only": "Header Only (e.g. OKTA)",
}


@st.cache_resource
def get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient(config=Config())


# ---------------------------------------------------------------------------
# Browse helpers
# ---------------------------------------------------------------------------
def list_all_http_servers(w: WorkspaceClient) -> list[dict]:
    """Return ALL HTTP connections, tagged as 'mcp' or 'rest'."""
    servers = []
    for conn in w.connections.list():
        if conn.connection_type and conn.connection_type.value == "HTTP":
            opts = conn.options or {}
            is_mcp = opts.get("is_mcp_connection") == "true"
            first_line = ""
            if conn.comment:
                for line in conn.comment.splitlines():
                    stripped = line.strip().strip("#").strip()
                    if stripped:
                        first_line = stripped
                        break
            servers.append({
                "name": conn.name,
                "host": opts.get("host", ""),
                "base_path": opts.get("base_path", ""),
                "comment": first_line,
                "owner": conn.owner or "",
                "type": "mcp" if is_mcp else "rest",
            })
    servers.sort(key=lambda c: c["name"])
    return servers


def _list_all_http_connections(w: WorkspaceClient) -> list[dict]:
    """Return all HTTP connections (MCP and non-MCP) — used by manage section."""
    connections = []
    for conn in w.connections.list():
        if conn.connection_type and conn.connection_type.value == "HTTP":
            connections.append({"name": conn.name, "owner": conn.owner or ""})
    connections.sort(key=lambda c: c["name"])
    return connections


def _read_existing_servers(w: WorkspaceClient, config_path: str) -> list[dict]:
    """Read the current selected_servers.json from the workspace."""
    try:
        with w.workspace.download(config_path) as f:
            return json.loads(f.read())
    except Exception:
        return []


def deploy_proxy_app(
    w: WorkspaceClient,
    selected_servers: list[dict],
    app_name: str,
) -> dict:
    """Merge new servers into existing selected_servers.json and redeploy."""
    config_path = f"{PROXY_SOURCE_PATH}/selected_servers.json"

    existing = _read_existing_servers(w, config_path)
    merged = {s["name"]: s for s in existing}
    for server in selected_servers:
        merged[server["name"]] = server
    existing = list(merged.values())

    config_content = json.dumps(existing, indent=2)

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
        w.apps.create_and_wait(App(name=app_name, description="Bundled MCP proxy server"))

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
# Create helpers
# ---------------------------------------------------------------------------
def build_connection_options(form: dict) -> dict[str, str]:
    """Build the options dict for connections.create() from the wizard form."""
    auth_type = form["auth_type"]
    opts: dict[str, str] = {
        "host": form["host"],
        "port": form["port"],
        "is_mcp_connection": "true" if form["is_mcp"] else "false",
    }
    if form.get("base_path"):
        opts["base_path"] = form["base_path"]

    if auth_type == "bearer":
        opts["bearer_token"] = form["bearer_token"]

    elif auth_type == "oauth_m2m":
        opts["client_id"] = form["client_id"]
        opts["client_secret"] = form["client_secret"]
        opts["oauth_scope"] = form["oauth_scope"]
        opts["token_endpoint"] = form["token_endpoint"]

    elif auth_type == "oauth_u2m_shared":
        opts["client_id"] = form["client_id"]
        opts["client_secret"] = form["client_secret"]
        opts["oauth_scope"] = form["oauth_scope"]
        opts["token_endpoint"] = form["token_endpoint"]
        opts["authorization_endpoint"] = form["authorization_endpoint"]

    elif auth_type == "oauth_u2m_per_user":
        opts["client_id"] = form["client_id"]
        opts["client_secret"] = form["client_secret"]
        opts["oauth_scope"] = form["oauth_scope"]
        opts["token_endpoint"] = form["token_endpoint"]
        opts["authorization_endpoint"] = form["authorization_endpoint"]
        if form.get("credential_exchange_method"):
            opts["oauth_credential_exchange_method"] = form["credential_exchange_method"]

    return opts


# ---------------------------------------------------------------------------
# Browse View
# ---------------------------------------------------------------------------
def browse_view(w: WorkspaceClient):
    st.markdown(
        "Browse all HTTP connections in this workspace. **MCP** servers are "
        "deployed via the proxy app. **REST** APIs are proxied through "
        "Unity Catalog connection proxy endpoints."
    )

    with st.spinner("Loading HTTP connections from workspace..."):
        connections = list_all_http_servers(w)

    if not connections:
        st.warning("No HTTP connections found in this workspace.")
        return

    mcp_count = sum(1 for c in connections if c["type"] == "mcp")
    rest_count = sum(1 for c in connections if c["type"] == "rest")

    col_search, col_type, col_owner = st.columns([3, 1, 1])
    with col_search:
        search = st.text_input(
            "Search",
            placeholder="e.g. tavily, airtable, slack",
            label_visibility="collapsed",
        )
    with col_type:
        type_filter = st.selectbox("Type", ["All", "MCP", "REST"])
    with col_owner:
        owner_filter = st.selectbox(
            "Owner",
            ["All"] + sorted({c["owner"] for c in connections if c["owner"]}),
        )

    filtered = connections
    if search:
        q = search.lower()
        filtered = [c for c in filtered if q in c["name"].lower() or q in c["host"].lower()]
    if type_filter != "All":
        filtered = [c for c in filtered if c["type"] == type_filter.lower()]
    if owner_filter != "All":
        filtered = [c for c in filtered if c["owner"] == owner_filter]

    if "selected" not in st.session_state:
        st.session_state.selected = set()

    # Summary bar
    sel_count = len(st.session_state.selected)
    col_stats, col_sel_all = st.columns([3, 1])
    with col_stats:
        st.caption(
            f"Showing **{len(filtered)}** of {len(connections)} connections "
            f"({mcp_count} MCP, {rest_count} REST) · **{sel_count} selected**"
        )
    with col_sel_all:
        if st.checkbox("Select all visible", key="select_all"):
            for c in filtered:
                st.session_state.selected.add(c["name"])

    # Card grid — 3 columns
    cols_per_row = 3
    for row_start in range(0, len(filtered), cols_per_row):
        row = filtered[row_start : row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for i, c in enumerate(row):
            with cols[i]:
                is_mcp = c["type"] == "mcp"
                badge_color = "#1E88E5" if is_mcp else "#FB8C00"
                badge_label = "MCP" if is_mcp else "REST"
                icon = "🔌" if is_mcp else "🌐"
                host_display = c["host"].replace("https://", "")
                base_path = c.get("base_path", "")

                with st.container(border=True):
                    st.markdown(
                        f"<span style='background:{badge_color};color:white;"
                        f"padding:2px 8px;border-radius:4px;font-size:0.75em;"
                        f"font-weight:600'>{badge_label}</span>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"### {icon} {c['name']}")
                    st.caption(f"`{host_display}{base_path}`")
                    if c.get("comment"):
                        st.caption(c["comment"][:80] + ("..." if len(c.get("comment", "")) > 80 else ""))
                    if c.get("owner"):
                        st.caption(f"Owner: {c['owner']}")

                    checked = st.checkbox(
                        "Select for deploy",
                        value=c["name"] in st.session_state.selected,
                        key=f"cb_{c['name']}",
                    )
                    if checked:
                        st.session_state.selected.add(c["name"])
                    else:
                        st.session_state.selected.discard(c["name"])

    st.markdown("---")

    # --- Split selected into MCP and REST ---
    conn_index = {c["name"]: c for c in connections}
    selected_mcp = [conn_index[n] for n in st.session_state.selected
                    if n in conn_index and conn_index[n]["type"] == "mcp"]
    selected_rest = [conn_index[n] for n in st.session_state.selected
                     if n in conn_index and conn_index[n]["type"] == "rest"]

    st.subheader("Deploy")

    proxy_app_name = st.text_input(
        "Proxy app name",
        value=MCP_PROXY_APP_NAME,
        help="Name for the Databricks App that will serve as the MCP proxy.",
    )

    # Review
    if selected_mcp or selected_rest:
        with st.expander(
            f"Review: {len(selected_mcp)} MCP server(s) + {len(selected_rest)} REST API(s)"
        ):
            if selected_mcp:
                st.markdown("**MCP servers** (JSON-RPC proxy):")
                for sc in selected_mcp:
                    st.markdown(f"- {sc['name']} → `{sc['host']}{sc['base_path']}`")
            if selected_rest:
                st.markdown("**REST APIs** (UC connection proxy):")
                for sc in selected_rest:
                    st.markdown(f"- {sc['name']} → `{sc['host']}{sc['base_path']}`")

    total_selected = len(selected_mcp) + len(selected_rest)
    can_deploy = total_selected > 0

    btn_label = f"Deploy {len(selected_mcp)} MCP + {len(selected_rest)} REST"
    deploy_btn = st.button(btn_label, disabled=not can_deploy, type="primary")

    if deploy_btn:
        with st.status("Deploying...", expanded=True) as status:
            all_proxy_servers: list[dict] = []

            if selected_mcp:
                st.write(f"Adding {len(selected_mcp)} MCP server(s)...")
                all_proxy_servers.extend(selected_mcp)

            if selected_rest:
                st.write(f"Adding {len(selected_rest)} REST API connection(s)...")
                for sc in selected_rest:
                    all_proxy_servers.append({
                        "name": sc["name"],
                        "type": "rest",
                        "connection_name": sc["name"],
                        "host": sc.get("host", ""),
                        "base_path": sc.get("base_path", ""),
                    })

            if all_proxy_servers:
                st.write("Deploying proxy app...")
                try:
                    result = deploy_proxy_app(w, all_proxy_servers, proxy_app_name)
                    st.success(f"Proxy app **{result['name']}** deployed!")
                    if result.get("url"):
                        st.markdown(f"**App URL:** [{result['url']}]({result['url']})")
                except Exception as e:
                    st.error(f"Proxy deployment failed: {e}")
                    st.exception(e)

            status.update(label="Deployment complete!", state="complete")
            st.balloons()

    # --- Manage connections ---
    st.markdown("---")
    with st.expander("Manage connections"):
        all_http = _list_all_http_connections(w)
        if all_http:
            del_name = st.selectbox(
                "Select connection to delete",
                [c["name"] for c in all_http],
                key="del_conn_select",
            )
            if st.button("Delete connection", type="primary", key="del_conn_btn"):
                try:
                    w.connections.delete(name=del_name)
                    st.success(f"Connection **{del_name}** deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete: {e}")


# ---------------------------------------------------------------------------
# Create View — multi-step wizard (mirrors Databricks Catalog Explorer UI)
# ---------------------------------------------------------------------------
STEP_LABELS = ["Connection basics", "Authentication", "Connection details"]


def _init_create_state():
    defaults = {"create_step": 0, "create_form": {}}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _step_indicator(current: int):
    cols = st.columns(len(STEP_LABELS))
    for i, label in enumerate(STEP_LABELS):
        with cols[i]:
            if i < current:
                st.markdown(f":white_check_mark: ~~{label}~~")
            elif i == current:
                st.markdown(f":arrow_forward: **{label}**")
            else:
                st.markdown(f":white_large_square: {label}")
    st.divider()


def _step_connection_basics():
    """Step 1: Connection name, type (HTTP), auth type, OAuth provider, comment."""
    form = st.session_state.create_form

    with st.container(border=True):
        st.caption("Step 1")
        st.subheader("Connection basics")
        st.divider()

        form["name"] = st.text_input(
            "Connection name*",
            value=form.get("name", ""),
        )

        st.selectbox(
            "Connection type*",
            ["HTTP"],
            disabled=True,
        )

        auth_label = st.selectbox(
            "Auth type*",
            AUTH_TYPE_OPTIONS,
            index=AUTH_TYPE_OPTIONS.index(form["auth_label"]) if form.get("auth_label") else 0,
        )
        form["auth_label"] = auth_label
        form["auth_type"] = AUTH_TYPE_KEYS[auth_label]

        is_oauth = form["auth_type"] != "bearer"
        if is_oauth:
            st.selectbox(
                "OAuth provider",
                OAUTH_PROVIDERS,
                help="Select a pre-configured OAuth provider or choose 'Manual configuration' to set up your own.",
            )

        form["comment"] = st.text_area(
            "Comment",
            value=form.get("comment", ""),
            height=100,
        )

    st.session_state.create_form = form
    can_proceed = bool(form.get("name"))

    col_l, col_r = st.columns([4, 1])
    with col_r:
        if st.button("Next →", disabled=not can_proceed, type="primary", key="basics_next"):
            st.session_state.create_step = 1
            st.rerun()


def _step_authentication():
    """Step 2: Credentials that vary by auth type."""
    form = st.session_state.create_form
    auth_type = form["auth_type"]
    auth_label = form.get("auth_label", "")

    with st.container(border=True):
        st.caption("Step 2")
        st.subheader("Authentication")
        st.markdown(f"**{auth_label}**")
        st.divider()

        if auth_type == "bearer":
            form["bearer_token"] = st.text_input(
                "Bearer Token*",
                type="password",
                value=form.get("bearer_token", ""),
                help="The authentication token included in request headers.",
            )
            can_proceed = bool(form.get("bearer_token"))

        elif auth_type == "oauth_m2m":
            form["client_id"] = st.text_input(
                "Client ID*",
                value=form.get("client_id", ""),
                help="Unique identifier for the application you created.",
            )
            form["client_secret"] = st.text_input(
                "Client secret*",
                type="password",
                value=form.get("client_secret", ""),
                help="Secret or password generated for the application.",
            )
            form["oauth_scope"] = st.text_input(
                "OAuth scope",
                value=form.get("oauth_scope", ""),
                help="Space-delimited, case-sensitive scopes. e.g. channels:read chat:write",
            )
            form["token_endpoint"] = st.text_input(
                "Token endpoint*",
                value=form.get("token_endpoint", ""),
                help="URL to obtain access tokens. e.g. https://auth.example.com/oauth/token",
            )
            can_proceed = all(form.get(k) for k in ["client_id", "client_secret", "token_endpoint"])

        elif auth_type == "oauth_u2m_shared":
            st.info(
                "You will be prompted to sign in. The credentials will be shared by "
                "all users of this connection. Some providers require adding "
                "`/login/oauth/http.html` to your redirect URL allowlist.",
                icon="ℹ️",
            )
            form["client_id"] = st.text_input(
                "Client ID*",
                value=form.get("client_id", ""),
            )
            form["client_secret"] = st.text_input(
                "Client secret*",
                type="password",
                value=form.get("client_secret", ""),
            )
            form["oauth_scope"] = st.text_input(
                "OAuth scope",
                value=form.get("oauth_scope", ""),
                help="Space-delimited scopes.",
            )
            form["authorization_endpoint"] = st.text_input(
                "Authorization endpoint*",
                value=form.get("authorization_endpoint", ""),
                help="e.g. https://auth.example.com/oauth/authorize",
            )
            form["token_endpoint"] = st.text_input(
                "Token endpoint*",
                value=form.get("token_endpoint", ""),
            )
            can_proceed = all(
                form.get(k)
                for k in ["client_id", "client_secret", "token_endpoint", "authorization_endpoint"]
            )

        elif auth_type == "oauth_u2m_per_user":
            st.info(
                "Each user will be prompted to sign in individually. "
                "Some providers require adding `/login/oauth/http.html` "
                "to your redirect URL allowlist.",
                icon="ℹ️",
            )
            form["client_id"] = st.text_input(
                "Client ID*",
                value=form.get("client_id", ""),
            )
            form["client_secret"] = st.text_input(
                "Client secret*",
                type="password",
                value=form.get("client_secret", ""),
            )
            form["oauth_scope"] = st.text_input(
                "OAuth scope",
                value=form.get("oauth_scope", ""),
            )
            form["authorization_endpoint"] = st.text_input(
                "Authorization endpoint*",
                value=form.get("authorization_endpoint", ""),
            )
            form["token_endpoint"] = st.text_input(
                "Token endpoint*",
                value=form.get("token_endpoint", ""),
            )
            form["credential_exchange_method"] = st.selectbox(
                "Credential exchange method",
                list(CREDENTIAL_EXCHANGE_METHODS.keys()),
                format_func=lambda k: CREDENTIAL_EXCHANGE_METHODS[k],
                help="How OAuth client credentials are passed during token exchange.",
            )
            can_proceed = all(
                form.get(k)
                for k in ["client_id", "client_secret", "token_endpoint", "authorization_endpoint"]
            )
        else:
            can_proceed = False

    st.session_state.create_form = form

    col_back, _, col_next = st.columns([1, 3, 1])
    with col_back:
        if st.button("← Back", key="auth_back"):
            st.session_state.create_step = 0
            st.rerun()
    with col_next:
        if st.button("Next →", disabled=not can_proceed, type="primary", key="auth_next"):
            st.session_state.create_step = 2
            st.rerun()


def _step_connection_details(w: WorkspaceClient):
    """Step 3: Host, port, base_path, MCP toggle."""
    form = st.session_state.create_form
    auth_type = form["auth_type"]

    with st.container(border=True):
        st.caption("Step 3")
        st.subheader("Connection details")
        st.divider()

        col_host, col_port = st.columns([4, 1])
        with col_host:
            form["host"] = st.text_input(
                "Host*",
                value=form.get("host", "https://"),
                help="Base URL of the external service. e.g. https://api.example.com",
            )
        with col_port:
            form["port"] = st.text_input(
                "Port",
                value=form.get("port", "443"),
            )

        form["base_path"] = st.text_input(
            "Base path",
            value=form.get("base_path", "/"),
            help="Root path appended to host. e.g. /api/v1 or /mcp",
        )

        form["is_mcp"] = st.toggle(
            "Register as MCP server",
            value=form.get("is_mcp", True),
            help="Enable to make this connection available as an MCP server.",
        )

    st.session_state.create_form = form

    can_create = bool(form.get("host") and form["host"] != "https://")

    with st.expander("Review configuration"):
        review = {
            "name": form.get("name", ""),
            "connection_type": "HTTP",
            "auth_type": form.get("auth_label", ""),
            "host": form.get("host", ""),
            "port": form.get("port", "443"),
            "base_path": form.get("base_path", ""),
            "is_mcp_connection": form.get("is_mcp", True),
        }
        if form.get("comment"):
            review["comment"] = form["comment"]
        st.json(review)

    col_back, _, col_create = st.columns([1, 3, 1])
    with col_back:
        if st.button("← Back", key="details_back"):
            st.session_state.create_step = 1
            st.rerun()
    with col_create:
        if st.button("Create connection", disabled=not can_create, type="primary", key="create_btn"):
            _create_connection(w, form)


def _create_connection(w: WorkspaceClient, form: dict):
    auth_label = form.get("auth_label", form.get("auth_type", ""))
    with st.status("Creating connection...", expanded=True) as status:
        try:
            options = build_connection_options(form)
            st.write(f"Creating **{form['name']}** (HTTP / {auth_label})...")

            conn = w.connections.create(
                name=form["name"],
                connection_type=ConnectionType.HTTP,
                options=options,
                comment=form.get("comment") or None,
            )

            status.update(label="Connection created!", state="complete")
            st.success(f"Connection **{conn.name}** created successfully!")

            st.session_state.create_step = 0
            st.session_state.create_form = {}
            st.balloons()

        except Exception as e:
            status.update(label="Creation failed", state="error")
            st.error(f"Failed to create connection: {e}")
            st.exception(e)


def create_view(w: WorkspaceClient):
    _init_create_state()
    _step_indicator(st.session_state.create_step)

    if st.session_state.create_step == 0:
        _step_connection_basics()
    elif st.session_state.create_step == 1:
        _step_authentication()
    elif st.session_state.create_step == 2:
        _step_connection_details(w)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="CDK MCP Registry",
        page_icon="🔌",
        layout="wide",
    )

    st.title("CDK MCP Registry")

    w = get_workspace_client()

    tab_browse, tab_create = st.tabs(["Browse & Deploy", "Create Connection"])

    with tab_browse:
        browse_view(w)

    with tab_create:
        create_view(w)


if __name__ == "__main__":
    main()
