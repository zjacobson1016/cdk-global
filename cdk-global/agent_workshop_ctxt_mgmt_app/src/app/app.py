"""
CDK Service Advisor — Context Management Demo
===============================================
Multi-page Dash app showing how page context (headers, titles, static &
dynamic data) flows into a per-page chatbot.  No real agent backend —
the chatbot simulates context-aware responses so stakeholders can see
exactly what information the agent would receive on each page.
"""

import json
import random
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html

from mock_data import (
    APPOINTMENTS,
    CHATBOT_RESPONSES,
    CUSTOMERS,
    DIAGNOSTIC_CODES,
    INSPECTION_ITEMS,
    PARTS_AVAILABILITY,
    RECOMMENDED_SERVICES,
    SERVICE_HISTORY,
    VEHICLES,
)

# ---------------------------------------------------------------------------
# App init
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.CYBORG,
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
    ],
    suppress_callback_exceptions=True,
    title="CDK Service Advisor",
)

app.index_string = """<!DOCTYPE html>
<html>
<head>
{%metas%}
<title>{%title%}</title>
{%favicon%}
{%css%}
<style>""" + """
/* Sidebar */
.sidebar { position: fixed; top: 0; left: 0; bottom: 0; width: 240px;
           background: #1a1d23; border-right: 1px solid #2d3139; z-index: 100;
           padding-top: 0; overflow-y: auto; }
.sidebar-brand { padding: 1.2rem 1rem; border-bottom: 1px solid #2d3139;
                 background: linear-gradient(135deg, #0d6efd22, #1a1d23); }
.sidebar-brand h5 { color: #0d6efd; margin: 0; font-weight: 700; font-size: 1rem; }
.sidebar-brand small { color: #6c757d; font-size: 0.7rem; }
.nav-item-custom { padding: 0.15rem 0.8rem; }
.nav-item-custom a { color: #adb5bd; border-radius: 8px; padding: 0.6rem 0.8rem;
                     display: flex; align-items: center; gap: 0.6rem;
                     text-decoration: none; transition: all 0.2s; font-size: 0.85rem; }
.nav-item-custom a:hover { color: #fff; background: #2d3139; }
.nav-item-custom a.active-nav { color: #fff; background: #0d6efd33;
                                border-left: 3px solid #0d6efd; }
.main-content { margin-left: 240px; padding: 1.5rem 1.5rem 1.5rem 1.5rem; }
.page-header { background: linear-gradient(135deg, #1e2126, #2d3139);
               border-radius: 12px; padding: 1.2rem 1.5rem; margin-bottom: 1.2rem;
               border: 1px solid #3d4149; }
.page-header h3 { margin: 0; color: #e9ecef; font-weight: 600; }
.page-header p { margin: 0.3rem 0 0 0; color: #8b929a; font-size: 0.85rem; }
.info-card { background: #1e2126; border: 1px solid #2d3139; border-radius: 10px; }
.info-card .card-header { background: transparent; border-bottom: 1px solid #2d3139;
                          font-weight: 600; color: #e9ecef; font-size: 0.85rem; }
.info-card .card-body { padding: 1rem; }
.chat-panel { background: #1e2126; border: 1px solid #2d3139; border-radius: 10px;
              display: flex; flex-direction: column; height: calc(100vh - 180px);
              position: sticky; top: 80px; }
.chat-messages { flex: 1; overflow-y: auto; padding: 1rem; }
.chat-msg { padding: 0.6rem 0.9rem; border-radius: 12px; margin-bottom: 0.6rem;
            font-size: 0.82rem; max-width: 90%; word-wrap: break-word; }
.chat-msg.user { background: #0d6efd; color: #fff; margin-left: auto; }
.chat-msg.bot  { background: #2d3139; color: #e0e0e0; }
.chat-input-area { padding: 0.8rem; border-top: 1px solid #2d3139; }
.context-panel { background: #12141a; border: 1px solid #2d3139; border-radius: 10px;
                 margin-bottom: 0.8rem; }
.context-json { font-family: 'Fira Code', monospace; font-size: 0.7rem;
                color: #98c379; white-space: pre-wrap; max-height: 260px;
                overflow-y: auto; padding: 0.8rem; margin: 0;
                background: #0d0f14; border-radius: 0 0 10px 10px; }
.badge-in-progress { background: #0d6efd; }
.badge-waiting { background: #ffc107; color: #000; }
.badge-scheduled { background: #6c757d; }
.badge-critical { background: #dc3545; }
.badge-required { background: #fd7e14; }
.badge-recommended { background: #20c997; }
.badge-investigate { background: #6f42c1; }
.data-row { display: flex; justify-content: space-between; padding: 0.35rem 0;
            border-bottom: 1px solid #2d313944; font-size: 0.82rem; }
.data-label { color: #8b929a; }
.data-value { color: #e9ecef; font-weight: 500; }
.queue-row { background: #1e2126; border: 1px solid #2d3139; border-radius: 8px;
             padding: 0.7rem 1rem; margin-bottom: 0.5rem; cursor: pointer;
             transition: all 0.2s; }
.queue-row:hover { border-color: #0d6efd; background: #1e212688; }
.section-tag { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1px;
               color: #6c757d; margin-bottom: 0.5rem; font-weight: 600; }
</style>
""" + """</head>
<body>
{%app_entry%}
<footer>
{%config%}
{%scripts%}
{%renderer%}
</footer>
</body>
</html>"""

PAGES = {
    "/": {"title": "Service Queue", "icon": "fa-clipboard-list", "desc": "Today's appointment queue and service bay status"},
    "/checkin": {"title": "Vehicle Check-In", "icon": "fa-car", "desc": "Active vehicle check-in with customer and vehicle details"},
    "/diagnostics": {"title": "Diagnostics", "icon": "fa-stethoscope", "desc": "Diagnostic codes, inspection results, and findings"},
    "/recommendations": {"title": "Recommendations", "icon": "fa-wrench", "desc": "Service recommendations, pricing, and parts availability"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def data_row(label: str, value, color: str | None = None) -> html.Div:
    style = {"color": color} if color else {}
    return html.Div([
        html.Span(label, className="data-label"),
        html.Span(str(value), className="data-value", style=style),
    ], className="data-row")


def status_badge(status: str) -> dbc.Badge:
    cls_map = {
        "In Progress": "badge-in-progress",
        "Waiting": "badge-waiting",
        "Scheduled": "badge-scheduled",
        "Critical": "badge-critical",
        "Required": "badge-required",
        "Recommended": "badge-recommended",
        "Investigate": "badge-investigate",
        "Replace": "badge-critical",
        "Monitor": "badge-waiting",
        "OK": "badge-recommended",
        "Due Now": "badge-critical",
        "Next Visit": "badge-waiting",
        "High": "badge-required",
        "Medium": "badge-waiting",
    }
    return dbc.Badge(status, className=cls_map.get(status, ""), style={"fontSize": "0.7rem"})


def info_card(title: str, children, icon: str = "") -> dbc.Card:
    header_children = []
    if icon:
        header_children.append(html.I(className=f"fas {icon} me-2", style={"color": "#0d6efd"}))
    header_children.append(title)
    return dbc.Card([
        dbc.CardHeader(header_children),
        dbc.CardBody(children),
    ], className="info-card mb-3")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def build_sidebar():
    nav_items = []
    for path, meta in PAGES.items():
        nav_items.append(html.Div(
            dcc.Link(
                [html.I(className=f"fas {meta['icon']}"), html.Span(meta["title"])],
                href=path,
                id=f"nav-{path.strip('/') or 'home'}",
                className="",
            ),
            className="nav-item-custom",
        ))
    return html.Div([
        html.Div([
            html.H5([html.I(className="fas fa-car-side me-2"), "CDK Service Advisor"]),
            html.Small("Context Management Demo"),
        ], className="sidebar-brand"),
        html.Div(nav_items, className="mt-3"),
        html.Div([
            html.Hr(style={"borderColor": "#2d3139"}),
            html.Div([
                html.I(className="fas fa-user-circle me-2", style={"color": "#0d6efd"}),
                html.Span("Mike Johnson", style={"color": "#adb5bd", "fontSize": "0.8rem"}),
            ], style={"padding": "0 1rem"}),
            html.Div([
                html.I(className="fas fa-building me-2", style={"color": "#6c757d"}),
                html.Span("Springfield Motors", style={"color": "#6c757d", "fontSize": "0.75rem"}),
            ], style={"padding": "0.3rem 1rem 1rem"}),
        ]),
    ], className="sidebar")


# ---------------------------------------------------------------------------
# Context inspector + chatbot
# ---------------------------------------------------------------------------
def build_chat_panel():
    return html.Div([
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="fas fa-code me-2", style={"color": "#98c379"}),
                    html.Span("Context Sent to Agent", style={"fontWeight": 600, "fontSize": "0.8rem", "color": "#e9ecef"}),
                ], style={"display": "flex", "alignItems": "center"}),
                dbc.Button(
                    html.I(className="fas fa-chevron-down"),
                    id="toggle-context",
                    size="sm",
                    color="link",
                    style={"color": "#6c757d", "padding": 0},
                ),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                       "padding": "0.7rem 1rem", "borderBottom": "1px solid #2d3139"}),
            dbc.Collapse(
                html.Pre(id="context-json-display", className="context-json", children="{}"),
                id="context-collapse",
                is_open=True,
            ),
        ], className="context-panel"),
        html.Div([
            html.Div([
                html.I(className="fas fa-robot me-2", style={"color": "#0d6efd"}),
                html.Span("Service Advisor AI", style={"fontWeight": 600, "fontSize": "0.85rem", "color": "#e9ecef"}),
                dbc.Badge("Demo Mode", color="warning", className="ms-2", style={"fontSize": "0.6rem"}),
            ], style={"padding": "0.8rem 1rem", "borderBottom": "1px solid #2d3139",
                       "display": "flex", "alignItems": "center"}),
            html.Div(id="chat-messages", className="chat-messages", children=[
                html.Div("👋 Hi! I'm the Service Advisor AI. I receive the page context shown above "
                          "with every message you send. Ask me anything about what's on this page!",
                          className="chat-msg bot"),
            ]),
            html.Div([
                dbc.InputGroup([
                    dbc.Input(id="chat-input", placeholder="Ask about this page...",
                              type="text", style={"background": "#12141a", "border": "1px solid #2d3139",
                                                   "color": "#e9ecef", "fontSize": "0.85rem"}),
                    dbc.Button(html.I(className="fas fa-paper-plane"), id="chat-send",
                               color="primary", size="sm"),
                ], size="sm"),
            ], className="chat-input-area"),
        ], className="chat-panel", style={"height": "auto", "minHeight": "350px"}),
    ])


# ---------------------------------------------------------------------------
# PAGE: Service Queue
# ---------------------------------------------------------------------------
def build_service_queue_page():
    today = datetime.now().strftime("%A, %B %d, %Y")
    queue_rows = []
    for apt in APPOINTMENTS:
        cust = CUSTOMERS[apt["customer_id"]]
        veh = VEHICLES[apt["vehicle_id"]]
        queue_rows.append(html.Div([
            html.Div([
                html.Div([
                    html.Span(apt["time"], style={"fontWeight": 600, "color": "#e9ecef", "fontSize": "0.9rem"}),
                    status_badge(apt["status"]),
                ], style={"display": "flex", "alignItems": "center", "gap": "0.6rem"}),
                html.Div(f"Bay {apt['bay']}" if apt["bay"] else "—",
                          style={"color": "#6c757d", "fontSize": "0.75rem"}),
            ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
            html.Div([
                html.Span(cust["name"], style={"color": "#e9ecef", "fontWeight": 500}),
                html.Span(" · ", style={"color": "#6c757d"}),
                html.Span(f"{veh['year']} {veh['make']} {veh['model']}", style={"color": "#adb5bd"}),
            ], style={"marginTop": "0.3rem", "fontSize": "0.82rem"}),
            html.Div(apt["type"], style={"color": "#0d6efd", "fontSize": "0.78rem", "marginTop": "0.2rem"}),
            html.Div(apt["notes"], style={"color": "#6c757d", "fontSize": "0.72rem", "marginTop": "0.2rem", "fontStyle": "italic"}) if apt["notes"] else None,
        ], className="queue-row"))

    in_progress = sum(1 for a in APPOINTMENTS if a["status"] == "In Progress")
    waiting = sum(1 for a in APPOINTMENTS if a["status"] == "Waiting")
    scheduled = sum(1 for a in APPOINTMENTS if a["status"] == "Scheduled")

    return html.Div([
        html.Div([
            html.Div("PAGE CONTEXT · STATIC", className="section-tag"),
            html.H3([html.I(className="fas fa-clipboard-list me-2"), "Service Queue"]),
            html.P(f"{today} · Springfield Motors · Advisor: Mike Johnson"),
        ], className="page-header"),
        dbc.Row([
            dbc.Col(info_card("Queue Summary", [
                data_row("Total Appointments", len(APPOINTMENTS)),
                data_row("In Progress", in_progress, "#0d6efd"),
                data_row("Waiting", waiting, "#ffc107"),
                data_row("Scheduled", scheduled, "#6c757d"),
                data_row("Est. Completion", "4:30 PM"),
            ], "fa-chart-bar"), width=4),
            dbc.Col(info_card("Bay Status", [
                data_row("Bay 1", "Available", "#20c997"),
                data_row("Bay 2", "Available", "#20c997"),
                data_row("Bay 3", "VH001 — Oil Change", "#0d6efd"),
                data_row("Bay 4", "Available", "#20c997"),
                data_row("Bay 5", "Maintenance", "#dc3545"),
            ], "fa-warehouse"), width=4),
            dbc.Col(info_card("Today's Revenue", [
                data_row("Completed", "$0.00"),
                data_row("In Progress", "$89.99"),
                data_row("Pending Estimates", "$2,340.00"),
                html.Hr(style={"borderColor": "#2d3139", "margin": "0.4rem 0"}),
                data_row("Projected Total", "$2,429.99", "#20c997"),
            ], "fa-dollar-sign"), width=4),
        ], className="mb-3"),
        html.Div("PAGE CONTEXT · DYNAMIC (via API)", className="section-tag"),
        info_card("Appointment Queue", queue_rows, "fa-list"),
    ])


# ---------------------------------------------------------------------------
# PAGE: Vehicle Check-In
# ---------------------------------------------------------------------------
def build_checkin_page(vehicle_id: str = "VH001"):
    veh = VEHICLES[vehicle_id]
    cust_id = next(cid for cid, c in CUSTOMERS.items() if c["vehicle_id"] == vehicle_id)
    cust = CUSTOMERS[cust_id]
    history = SERVICE_HISTORY.get(cust_id, [])
    apt = next((a for a in APPOINTMENTS if a["vehicle_id"] == vehicle_id), None)

    return html.Div([
        html.Div([
            html.Div("PAGE CONTEXT · STATIC", className="section-tag"),
            html.H3([html.I(className="fas fa-car me-2"), "Vehicle Check-In"]),
            html.P(f"Checking in {veh['year']} {veh['make']} {veh['model']} for {cust['name']}"),
        ], className="page-header"),
        dbc.Row([
            dbc.Col([
                info_card("Customer Information", [
                    data_row("Name", cust["name"]),
                    data_row("Phone", cust["phone"]),
                    data_row("Email", cust["email"]),
                    data_row("Preferred Contact", cust["preferred_contact"]),
                    data_row("Loyalty Tier", cust["loyalty_tier"],
                             "#ffc107" if cust["loyalty_tier"] == "Gold" else
                             "#0dcaf0" if cust["loyalty_tier"] == "Platinum" else "#adb5bd"),
                    data_row("Total Visits", cust["total_visits"]),
                    data_row("Lifetime Value", f"${cust['lifetime_value']:,.2f}"),
                ], "fa-user"),
            ], width=6),
            dbc.Col([
                info_card("Vehicle Details", [
                    data_row("VIN", veh["vin"]),
                    data_row("Year / Make / Model", f"{veh['year']} {veh['make']} {veh['model']} {veh['trim']}"),
                    data_row("Color", veh["color"]),
                    data_row("Mileage", f"{veh['mileage']:,} mi"),
                    data_row("Engine", veh["engine"]),
                    data_row("Transmission", veh["transmission"]),
                    data_row("License Plate", veh["license_plate"]),
                ], "fa-id-card"),
            ], width=6),
        ]),
        dbc.Row([
            dbc.Col([
                html.Div("PAGE CONTEXT · DYNAMIC (via API)", className="section-tag"),
                info_card("Appointment Details", [
                    data_row("Service Type", apt["type"] if apt else "Walk-in"),
                    data_row("Advisor", apt["advisor"] if apt else "—"),
                    data_row("Estimated Duration", apt["estimated_duration"] if apt else "TBD"),
                    data_row("Customer Notes", apt["notes"] if apt else "None"),
                ] if apt else [html.P("No appointment found", style={"color": "#6c757d"})], "fa-calendar-check"),
            ], width=6),
            dbc.Col([
                info_card("Service History", [
                    html.Div([
                        html.Div([
                            html.Span(h["date"], style={"color": "#6c757d", "fontSize": "0.75rem", "minWidth": "80px"}),
                            html.Span(h["service"], style={"color": "#e9ecef", "fontSize": "0.8rem", "flex": 1}),
                            html.Span(f"${h['cost']:.2f}", style={"color": "#20c997", "fontSize": "0.8rem"}),
                        ], style={"display": "flex", "gap": "0.8rem", "padding": "0.4rem 0",
                                  "borderBottom": "1px solid #2d313944"}),
                    ]) for h in history
                ] if history else [html.P("No service history", style={"color": "#6c757d", "fontSize": "0.8rem"})],
                "fa-history"),
            ], width=6),
        ]),
    ])


# ---------------------------------------------------------------------------
# PAGE: Diagnostics
# ---------------------------------------------------------------------------
def build_diagnostics_page(vehicle_id: str = "VH002"):
    veh = VEHICLES[vehicle_id]
    codes = DIAGNOSTIC_CODES.get(vehicle_id, [])
    items = INSPECTION_ITEMS.get(vehicle_id, [])

    code_rows = []
    for c in codes:
        code_rows.append(html.Div([
            html.Div([
                html.Code(c["code"], style={"color": "#e5c07b", "fontWeight": 700, "fontSize": "0.85rem"}),
                status_badge(c["severity"]),
            ], style={"display": "flex", "alignItems": "center", "gap": "0.5rem"}),
            html.Div(c["description"], style={"color": "#e9ecef", "fontSize": "0.8rem", "marginTop": "0.2rem"}),
            html.Div(f"System: {c['system']}", style={"color": "#6c757d", "fontSize": "0.72rem"}),
        ], style={"padding": "0.6rem 0", "borderBottom": "1px solid #2d313944"}))

    inspection_rows = []
    for item in items:
        inspection_rows.append(html.Div([
            html.Div([
                html.Span(item["item"], style={"color": "#e9ecef", "fontSize": "0.82rem", "flex": 1}),
                status_badge(item["status"]),
                status_badge(item["urgency"]) if item["urgency"] != "None" else None,
            ], style={"display": "flex", "alignItems": "center", "gap": "0.4rem"}),
            html.Div(item["notes"], style={"color": "#6c757d", "fontSize": "0.72rem", "marginTop": "0.15rem"}),
        ], style={"padding": "0.5rem 0", "borderBottom": "1px solid #2d313944"}))

    return html.Div([
        html.Div([
            html.Div("PAGE CONTEXT · STATIC", className="section-tag"),
            html.H3([html.I(className="fas fa-stethoscope me-2"), "Diagnostic Report"]),
            html.P(f"{veh['year']} {veh['make']} {veh['model']} — VIN: {veh['vin']}"),
        ], className="page-header"),
        html.Div([
            html.Label("Select Vehicle", style={"color": "#8b929a", "fontSize": "0.8rem", "marginBottom": "0.3rem"}),
            dcc.Dropdown(
                id="diag-vehicle-select",
                options=[{"label": f"{v['year']} {v['make']} {v['model']} ({vid})", "value": vid}
                         for vid, v in VEHICLES.items()],
                value=vehicle_id,
                style={"backgroundColor": "#1e2126", "fontSize": "0.85rem"},
                className="mb-3",
            ),
        ]),
        dbc.Row([
            dbc.Col([
                html.Div("PAGE CONTEXT · DYNAMIC (via API)", className="section-tag"),
                info_card(f"DTC Codes ({len(codes)} found)", code_rows if code_rows else [
                    html.P("No diagnostic codes found", style={"color": "#20c997", "fontSize": "0.8rem"}),
                    html.I(className="fas fa-check-circle", style={"color": "#20c997", "fontSize": "1.5rem"}),
                ], "fa-exclamation-triangle"),
            ], width=5),
            dbc.Col([
                info_card(f"Multi-Point Inspection ({len(items)} items)", inspection_rows if inspection_rows else [
                    html.P("No inspection data available", style={"color": "#6c757d", "fontSize": "0.8rem"}),
                ], "fa-clipboard-check"),
            ], width=7),
        ]),
    ])


# ---------------------------------------------------------------------------
# PAGE: Recommendations
# ---------------------------------------------------------------------------
def build_recommendations_page(vehicle_id: str = "VH002"):
    veh = VEHICLES[vehicle_id]
    recs = RECOMMENDED_SERVICES.get(vehicle_id, [])
    cust_id = next((cid for cid, c in CUSTOMERS.items() if c["vehicle_id"] == vehicle_id), None)
    cust = CUSTOMERS[cust_id] if cust_id else None

    total = sum(r["price"] for r in recs)
    critical = sum(1 for r in recs if r["priority"] == "Critical")
    required = sum(1 for r in recs if r["priority"] == "Required")

    rec_rows = []
    for r in recs:
        rec_rows.append(dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Span(r["service"], style={"color": "#e9ecef", "fontWeight": 600, "fontSize": "0.85rem", "flex": 1}),
                    status_badge(r["priority"]),
                    html.Span(f"${r['price']:.2f}", style={"color": "#20c997", "fontWeight": 600, "fontSize": "0.9rem"}),
                ], style={"display": "flex", "alignItems": "center", "gap": "0.6rem"}),
                html.Div(r["reason"], style={"color": "#8b929a", "fontSize": "0.75rem", "marginTop": "0.3rem"}),
            ], style={"padding": "0.7rem 1rem"}),
        ], className="info-card mb-2"))

    parts_rows = []
    for part, info in PARTS_AVAILABILITY.items():
        parts_rows.append(html.Div([
            html.Span(part, style={"color": "#e9ecef", "fontSize": "0.78rem", "flex": 1}),
            dbc.Badge("In Stock" if info["in_stock"] else info["eta"],
                      color="success" if info["in_stock"] else "warning",
                      style={"fontSize": "0.65rem"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "0.5rem",
                  "padding": "0.35rem 0", "borderBottom": "1px solid #2d313944"}))

    return html.Div([
        html.Div([
            html.Div("PAGE CONTEXT · STATIC", className="section-tag"),
            html.H3([html.I(className="fas fa-wrench me-2"), "Service Recommendations"]),
            html.P(f"{veh['year']} {veh['make']} {veh['model']} — {cust['name'] if cust else 'Unknown Customer'}"),
        ], className="page-header"),
        html.Div([
            html.Label("Select Vehicle", style={"color": "#8b929a", "fontSize": "0.8rem", "marginBottom": "0.3rem"}),
            dcc.Dropdown(
                id="rec-vehicle-select",
                options=[{"label": f"{v['year']} {v['make']} {v['model']} ({vid})", "value": vid}
                         for vid, v in VEHICLES.items() if vid in RECOMMENDED_SERVICES],
                value=vehicle_id,
                style={"backgroundColor": "#1e2126", "fontSize": "0.85rem"},
                className="mb-3",
            ),
        ]),
        dbc.Row([
            dbc.Col([
                info_card("Estimate Summary", [
                    data_row("Total Services", len(recs)),
                    data_row("Critical Items", critical, "#dc3545"),
                    data_row("Required Items", required, "#fd7e14"),
                    html.Hr(style={"borderColor": "#2d3139", "margin": "0.4rem 0"}),
                    data_row("Estimated Total", f"${total:,.2f}", "#20c997"),
                    html.Div([
                        dbc.Button("Approve All", color="success", size="sm", className="me-2 mt-2", id="approve-all-btn"),
                        dbc.Button("Approve Critical Only", color="warning", size="sm", className="mt-2", id="approve-critical-btn"),
                    ]),
                ], "fa-calculator"),
            ], width=4),
            dbc.Col([
                html.Div("PAGE CONTEXT · DYNAMIC (via API)", className="section-tag"),
                info_card(f"Recommended Services ({len(recs)})", rec_rows if rec_rows else [
                    html.P("No recommendations for this vehicle", style={"color": "#6c757d"}),
                ], "fa-tools"),
            ], width=8),
        ]),
        dbc.Row([
            dbc.Col([
                info_card("Parts Availability", parts_rows, "fa-boxes-stacked"),
            ], width=12),
        ]),
    ])


# ---------------------------------------------------------------------------
# Context builders — assemble what would be sent to the agent
# ---------------------------------------------------------------------------
def build_context(page: str, vehicle_id: str | None = None) -> dict:
    base = {
        "page": {
            "title": PAGES.get(page, {}).get("title", "Unknown"),
            "description": PAGES.get(page, {}).get("desc", ""),
            "url_path": page,
        },
        "user": {"name": "Mike Johnson", "role": "Service Advisor", "dealership": "Springfield Motors"},
        "timestamp": datetime.now().isoformat(),
    }

    if page == "/":
        base["static_data"] = {
            "total_appointments": len(APPOINTMENTS),
            "in_progress": sum(1 for a in APPOINTMENTS if a["status"] == "In Progress"),
            "waiting": sum(1 for a in APPOINTMENTS if a["status"] == "Waiting"),
            "scheduled": sum(1 for a in APPOINTMENTS if a["status"] == "Scheduled"),
        }
        base["dynamic_data"] = {
            "appointments": [
                {
                    "customer": CUSTOMERS[a["customer_id"]]["name"],
                    "vehicle": f"{VEHICLES[a['vehicle_id']]['year']} {VEHICLES[a['vehicle_id']]['make']} {VEHICLES[a['vehicle_id']]['model']}",
                    "service_type": a["type"],
                    "status": a["status"],
                    "time": a["time"],
                    "notes": a["notes"],
                }
                for a in APPOINTMENTS
            ],
        }

    elif page == "/checkin":
        vid = vehicle_id or "VH001"
        veh = VEHICLES.get(vid, {})
        cust_id = next((cid for cid, c in CUSTOMERS.items() if c["vehicle_id"] == vid), None)
        cust = CUSTOMERS.get(cust_id, {}) if cust_id else {}
        apt = next((a for a in APPOINTMENTS if a["vehicle_id"] == vid), None)
        base["static_data"] = {
            "customer": {k: v for k, v in cust.items() if k != "vehicle_id"},
            "vehicle": veh,
        }
        base["dynamic_data"] = {
            "appointment": {k: v for k, v in apt.items() if k not in ("customer_id", "vehicle_id")} if apt else None,
            "service_history": SERVICE_HISTORY.get(cust_id, []),
        }

    elif page == "/diagnostics":
        vid = vehicle_id or "VH002"
        veh = VEHICLES.get(vid, {})
        base["static_data"] = {"vehicle": veh}
        base["dynamic_data"] = {
            "dtc_codes": DIAGNOSTIC_CODES.get(vid, []),
            "inspection_items": INSPECTION_ITEMS.get(vid, []),
        }

    elif page == "/recommendations":
        vid = vehicle_id or "VH002"
        veh = VEHICLES.get(vid, {})
        recs = RECOMMENDED_SERVICES.get(vid, [])
        cust_id = next((cid for cid, c in CUSTOMERS.items() if c["vehicle_id"] == vid), None)
        cust = CUSTOMERS.get(cust_id, {}) if cust_id else {}
        base["static_data"] = {
            "vehicle": veh,
            "customer": {k: v for k, v in cust.items() if k != "vehicle_id"} if cust else None,
        }
        base["dynamic_data"] = {
            "recommendations": recs,
            "estimate_total": sum(r["price"] for r in recs),
            "critical_count": sum(1 for r in recs if r["priority"] == "Critical"),
            "parts_availability": PARTS_AVAILABILITY,
        }

    return base


def generate_chat_response(page: str, user_msg: str, context: dict) -> str:
    """Simulated agent response that references the page context."""
    page_key = page.strip("/") or "service_queue"
    key_map = {
        "": "service_queue",
        "checkin": "vehicle_checkin",
        "diagnostics": "diagnostics",
        "recommendations": "recommendations",
    }
    key = key_map.get(page_key, "service_queue")
    templates = CHATBOT_RESPONSES.get(key, [])

    if not templates:
        return "I have your page context but no templates for this page. In production, an LLM agent would generate a contextual response here."

    template = random.choice(templates)

    try:
        if key == "service_queue":
            sd = context.get("static_data", {})
            dd = context.get("dynamic_data", {})
            apts = dd.get("appointments", [])
            first_waiting = next((a for a in apts if a["status"] == "Waiting"), {})
            return template.format(
                count=sd.get("total_appointments", 0),
                in_progress=sd.get("in_progress", 0),
                waiting=sd.get("waiting", 0),
                customer=first_waiting.get("customer", "N/A"),
                vehicle=first_waiting.get("vehicle", "N/A"),
            )
        elif key == "vehicle_checkin":
            sd = context.get("static_data", {})
            dd = context.get("dynamic_data", {})
            cust = sd.get("customer", {})
            veh = sd.get("vehicle", {})
            apt = dd.get("appointment", {})
            hist = dd.get("service_history", [])
            return template.format(
                customer=cust.get("name", "Unknown"),
                tier=cust.get("loyalty_tier", "Standard"),
                visits=cust.get("total_visits", 0),
                vehicle=f"{veh.get('year', '')} {veh.get('make', '')} {veh.get('model', '')}",
                service_type=apt.get("type", "General") if apt else "General",
                mileage=f"{veh.get('mileage', 0):,}",
                last_service=hist[0]["service"] if hist else "no prior service",
            )
        elif key == "diagnostics":
            dd = context.get("dynamic_data", {})
            codes = dd.get("dtc_codes", [])
            items = dd.get("inspection_items", [])
            top = codes[0] if codes else {"code": "None", "description": "N/A", "system": "N/A"}
            replace_items = [i["item"] for i in items if i.get("status") == "Replace"]
            return template.format(
                code_count=len(codes),
                top_code=top.get("code", "N/A"),
                top_desc=top.get("description", "N/A"),
                system=top.get("system", "N/A"),
                findings=", ".join(replace_items) if replace_items else "No immediate replacements",
            )
        elif key == "recommendations":
            dd = context.get("dynamic_data", {})
            recs = dd.get("recommendations", [])
            total = dd.get("estimate_total", 0)
            critical = dd.get("critical_count", 0)
            parts = dd.get("parts_availability", {})
            in_stock_count = sum(1 for p in parts.values() if p.get("in_stock"))
            return template.format(
                rec_count=len(recs),
                total=total,
                critical=critical,
                in_stock=in_stock_count,
                backorder=len(parts) - in_stock_count,
            )
    except (KeyError, IndexError, TypeError):
        pass

    return (
        f"[Context received: {len(json.dumps(context))} bytes] "
        f"I'm processing your question \"{user_msg}\" with full page context from the "
        f"{context.get('page', {}).get('title', 'current')} page. "
        "In production, an LLM agent would use this context to give a precise answer."
    )


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Store(id="current-vehicle", data="VH001"),
    dcc.Store(id="chat-history", data=[]),
    dcc.Store(id="page-context", data={}),
    build_sidebar(),
    html.Div([
        dbc.Row([
            dbc.Col(html.Div(id="page-content"), width=8, style={"paddingRight": "0.5rem"}),
            dbc.Col(build_chat_panel(), width=4),
        ]),
    ], className="main-content"),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("page-content", "children"),
    Output("page-context", "data"),
    Input("url", "pathname"),
    Input("current-vehicle", "data"),
)
def render_page(pathname, vehicle_id):
    page = pathname or "/"
    if page == "/":
        content = build_service_queue_page()
    elif page == "/checkin":
        content = build_checkin_page(vehicle_id or "VH001")
    elif page == "/diagnostics":
        content = build_diagnostics_page(vehicle_id or "VH002")
    elif page == "/recommendations":
        content = build_recommendations_page(vehicle_id or "VH002")
    else:
        content = build_service_queue_page()
        page = "/"

    context = build_context(page, vehicle_id)
    return content, context


@callback(
    Output("context-json-display", "children"),
    Input("page-context", "data"),
)
def update_context_display(context):
    return json.dumps(context, indent=2, default=str)


@callback(
    Output("context-collapse", "is_open"),
    Input("toggle-context", "n_clicks"),
    State("context-collapse", "is_open"),
    prevent_initial_call=True,
)
def toggle_context(n, is_open):
    return not is_open


@callback(
    Output("chat-messages", "children"),
    Output("chat-input", "value"),
    Output("chat-history", "data"),
    Input("chat-send", "n_clicks"),
    Input("chat-input", "n_submit"),
    State("chat-input", "value"),
    State("chat-history", "data"),
    State("page-context", "data"),
    State("url", "pathname"),
    prevent_initial_call=True,
)
def handle_chat(n_clicks, n_submit, message, history, context, pathname):
    if not message or not message.strip():
        raise dash.exceptions.PreventUpdate

    history = history or []
    history.append({"role": "user", "text": message.strip()})

    response = generate_chat_response(pathname or "/", message.strip(), context)
    history.append({"role": "bot", "text": response})

    msgs = [
        html.Div(
            "👋 Hi! I'm the Service Advisor AI. I receive the page context shown above "
            "with every message you send. Ask me anything about what's on this page!",
            className="chat-msg bot",
        )
    ]
    for h in history:
        msgs.append(html.Div(h["text"], className=f"chat-msg {h['role']}"))

    return msgs, "", history


@callback(
    Output("current-vehicle", "data"),
    Input("diag-vehicle-select", "value"),
    Input("rec-vehicle-select", "value"),
    prevent_initial_call=True,
)
def update_vehicle(diag_val, rec_val):
    trigger = ctx.triggered_id
    if trigger == "diag-vehicle-select" and diag_val:
        return diag_val
    if trigger == "rec-vehicle-select" and rec_val:
        return rec_val
    raise dash.exceptions.PreventUpdate


# Active-nav highlighting
for path in PAGES:
    nav_id = f"nav-{path.strip('/') or 'home'}"

    @callback(
        Output(nav_id, "className"),
        Input("url", "pathname"),
        prevent_initial_call=False,
    )
    def set_active(pathname, _path=path):
        return "active-nav" if pathname == _path else ""


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
