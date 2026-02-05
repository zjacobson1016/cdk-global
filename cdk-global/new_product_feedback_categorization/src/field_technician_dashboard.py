import dash
from dash import dcc, html, Input, Output, State, callback_context, dash_table
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import uuid
import json
import os
import getpass
from flask import request
from database_operations import QuoteDatabase
from openai import OpenAI
mas_endpoint = os.getenv("MAS_ENDPOINT")
databricks_client_id = os.getenv("DATABRICKS_CLIENT_ID")
# Initialize the Dash app with Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME])
app.title = "Manufacturing Automated Quote Management Dashboard"

def get_current_user():
    """
    Get the current user from various sources depending on deployment environment.
    Returns the user identifier (email or username).
    """
    # Method 2: Check Flask request headers (common in enterprise deployments)
    try:
        if hasattr(request, 'headers'):
            # Common headers used by authentication proxies
            user_headers = [
                'X-Forwarded-User',      # Common proxy header
                'X-Remote-User',         # Apache mod_auth header
                'X-Authenticated-User',  # Custom auth header
                'HTTP_X_FORWARDED_USER', # Alternative format
                'REMOTE_USER',           # CGI/WSGI standard
                'Authorization-User',    # Custom authorization header
            ]
            
            for header in user_headers:
                user = request.headers.get(header)
                if user:
                    return user.strip()
    except:
        pass
    
    # Method 3: Check environment variables (development/testing)
    env_vars = [
        'USER',           # Unix username
        'USERNAME',       # Windows username  
        'LOGNAME',        # Alternative Unix
        'DASH_USER',      # Custom environment variable
        'APP_USER',       # Application-specific user
    ]
    
    for var in env_vars:
        user = os.environ.get(var)
        if user:
            return user
 

def get_user_display_name(user_id):
    """
    Convert user ID to a display-friendly name.
    You can extend this to look up names from a database or directory service.
    """
    # if not user_id or user_id == "unknown_user":
    #     return "Anonymous User"
    
    # # If it's an email, extract the name part
    # if "@" in user_id:
    #     name_part = user_id.split("@")[0]
    #     # Convert dots/underscores to spaces and title case
    #     return name_part.replace(".", " ").replace("_", " ").title()
    
    # For non-email usernames, just title case
    return os.getenv("DATABRICKS_CLIENT_ID")

# Get current user at app startup
current_user = get_current_user()
user_display_name = get_user_display_name(current_user)

print(f"📱 Dashboard started for user: {current_user} ({user_display_name})")

# Initialize database connection with current user
try:
    db = QuoteDatabase(user=databricks_client_id)
    
    print(f"✅ Quote database connection initialized for user: {current_user}")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    db = None

# Initialize Databricks AI client for technical assistant
try:
    DATABRICKS_CLIENT_ID = os.getenv("DATABRICKS_CLIENT_ID")
    if not DATABRICKS_CLIENT_ID:
        raise ValueError("DATABRICKS_CLIENT_ID environment variable is not set")
    
    ai_client = OpenAI(
        api_key=DATABRICKS_CLIENT_ID,
        base_url=f"https://{os.getenv('DATABRICKS_HOST')}/serving-endpoints"
    )
    print("✅ Databricks AI client initialized")
except Exception as e:
    print(f"❌ AI client initialization failed: {e}")
    ai_client = None

# Sample chat history
chat_history = [
    {"role": "assistant", "content": "Hello! I'm your Manufacturing technical assistant. How can I help you today?"}
]

# App layout
app.layout = dbc.Container([
    # Header
    dbc.Row([
        dbc.Col([
            html.H1([
                html.I(className="fas fa-tools me-3"),
                "Manufacturing Automated Quote Management Dashboard"
            ], className="text-primary mb-0"),
            html.P("Automated quote processing and approval workflow", className="text-muted")
        ], width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6([
                        html.I(className="fas fa-user me-2"),
                        "Current User"
                    ], className="text-muted mb-1"),
                    html.H5(user_display_name, className="mb-0"),
                    html.Small(current_user, className="text-muted")
                ], className="text-center")
            ], color="light", outline=True)
        ], width=4)
    ], className="mb-4"),
    
    # Navigation tabs
    dcc.Tabs(id="main-tabs", value="quotes", children=[
        dcc.Tab(label="Automated Quotes", value="quotes", children=[
            html.Div(id="quotes-content")
        ]),
        dcc.Tab(label="Technical Assistant", value="chatbot", children=[
            html.Div(id="chatbot-content")
        ]),
        dcc.Tab(label="Dashboard View", value="dashboard", children=[
            html.Div(id="dashboard-content")
        ])
    ]),
    
    # Hidden divs for storing data
    html.Div(id="chat-store", children=json.dumps(chat_history), style={"display": "none"}),
    html.Div(id="selected-quote-id", children="", style={"display": "none"}),
    dcc.Interval(id="quote-refresh", interval=15*1000, n_intervals=0),  # Refresh every 30 seconds
    html.Div(id="quote-selection-trigger", style={"display": "none"}),  # Hidden trigger for quote selection
    
], fluid=True, className="py-4")

# Dynamic user detection callback (useful if user can change during session)
@app.callback(
    Output("selected-quote-id", "children", allow_duplicate=True),
    [Input("quote-refresh", "n_intervals")],
    prevent_initial_call=True
)
def update_user_context(n_intervals):
    """
    Callback to dynamically update user context.
    This runs periodically and can detect user changes.
    """
    try:
        # Get current user dynamically (useful for shared environments)
        dynamic_user = get_current_user()
        
        # You could update global variables or trigger other updates here
        # For example, updating user-specific data or permissions
        
        # For now, just log if user changed
        global current_user
        if dynamic_user != current_user:
            print(f"🔄 User changed from {current_user} to {dynamic_user}")
            current_user = dynamic_user
            
    except Exception as e:
        print(f"⚠️ Error updating user context: {e}")
    
    # Return no update to avoid interfering with quote selection
    raise PreventUpdate

# Clientside callback to handle quote selection
app.clientside_callback(
    """
    function(n_clicks_list, id_list) {
        const ctx = window.dash_clientside.callback_context;
        if (!ctx.triggered.length) {
            return window.dash_clientside.no_update;
        }
        
        // Get the quote ID from the triggered button
        const button_id = JSON.parse(ctx.triggered[0].prop_id.split('.')[0]);
        return button_id.index;
    }
    """,
    Output("selected-quote-id", "children"),
    [Input({"type": "select-quote", "index": dash.ALL}, "n_clicks")],
    [State({"type": "select-quote", "index": dash.ALL}, "id")]
)

# Quotes tab content
def create_quotes_content():
    return dbc.Row([
        # Automated quotes list
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4([
                        html.I(className="fas fa-file-invoice-dollar me-2"),
                        "Automated Quotes"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    html.Div(id="quotes-list")
                ])
            ])
        ], width=8),
        
        # Quote approval panel
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4([
                        html.I(className="fas fa-check-circle me-2"),
                        "Quote Review"
                    ], className="mb-0")
                ]),
                dbc.CardBody([
                    html.Div(id="quote-review-panel")
                ])
            ])
        ], width=4)
    ])

# Chatbot tab content
def create_chatbot_content():
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4([
                        html.I(className="fas fa-robot me-2"),
                        "Technical Assistant"
                    ], className="mb-0"),
                    html.Small("Search internal documents and get technical support", className="text-muted")
                ]),
                dbc.CardBody([
                    # Chat history display
                    html.Div([
                        html.Div(id="chat-history", style={
                            "height": "400px",
                            "overflow-y": "auto",
                            "border": "1px solid #dee2e6",
                            "border-radius": "0.375rem",
                            "padding": "1rem",
                            "margin-bottom": "1rem",
                            "background-color": "#f8f9fa"
                        }),
                        # Loading indicator for chatbot processing
                        html.Div(
                            id="chat-loading",
                            children=[
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Spinner(
                                            html.Div([
                                                html.I(className="fas fa-robot me-2 text-primary"),
                                                html.Span("Assistant is searching knowledge base...", className="text-primary")
                                            ]), 
                                            size="sm", 
                                            color="primary"
                                        )
                                    ], className="text-center")
                                ], className="mb-2"),
                                dbc.Progress(
                                    animated=True, 
                                    striped=True, 
                                    color="info", 
                                    style={"height": "6px"}
                                )
                            ],
                            style={"display": "none"},
                            className="mb-3 p-3 bg-light rounded border-start border-primary border-3"
                        ),
                        # Chat input
                        dbc.InputGroup([
                            dbc.Input(
                                id="chat-input",
                                placeholder="Ask about equipment, procedures, or troubleshooting...",
                                type="text",
                                disabled=False
                            ),
                            dbc.Button([
                                html.I(className="fas fa-paper-plane", id="send-icon")
                            ], id="send-button", color="primary", disabled=False)
                        ])
                    ])
                ])
            ])
        ], width=12)
    ])

# Dashboard tab content
def create_dashboard_content():
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H4([
                        html.I(className="fas fa-chart-line me-2"),
                        "Analytics Dashboard"
                    ], className="mb-0"),
                    html.Small("Real-time operational metrics and insights", className="text-muted")
                ]),
                dbc.CardBody([
                    html.Iframe(
                        src="https://e2-dogfood.staging.cloud.databricks.com/embed/dashboardsv3/01f0c96b12ab15e8b4f792c4c5eaf3c1?o=6051921418418893",
                        style={
                            "width": "100%",
                            "height": "600px",
                            "border": "none",
                            "border-radius": "0.375rem"
                        }
                    )
                    
                ], className="p-0")  # Remove padding to make iframe fill card
            ])
        ], width=12)
    ])

# Callback for tab content
@app.callback(
    [Output("quotes-content", "children"),
     Output("chatbot-content", "children"),
     Output("dashboard-content", "children")],
    [Input("main-tabs", "value")]
)
def render_tab_content(active_tab):
    quotes_content = create_quotes_content() if active_tab == "quotes" else html.Div()
    chatbot_content = create_chatbot_content() if active_tab == "chatbot" else html.Div()
    dashboard_content = create_dashboard_content() if active_tab == "dashboard" else html.Div()
    return quotes_content, chatbot_content, dashboard_content

# Callback for quotes list
@app.callback(
    Output("quotes-list", "children"),
    [Input("quote-refresh", "n_intervals")]
)
def update_quotes_list(n_intervals):
    if not db:
        return dbc.Alert("Database connection unavailable", color="danger")
    
    try:
        quotes = db.get_all_quotes()
    except Exception as e:
        return dbc.Alert(f"Error loading quotes: {str(e)}", color="danger")
    
    if not quotes:
        return dbc.Alert("No automated quotes available", color="info")
    
    quote_cards = []
    for quote in quotes:
        created_time = datetime.fromisoformat(quote["created"]) if isinstance(quote["created"], str) else quote["created"]
        
        # Priority badge color
        priority_color = {
            "High": "danger",
            "Medium": "warning", 
            "Low": "info"
        }.get(quote["priority"], "secondary")
        
        # Status badge color
        status_color = {
            "Pending": "warning",
            "Approved": "success",
            "Denied": "danger",
            "Delivered": "info"
        }.get(quote["status"], "secondary")
        
        card = dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H5([
                            quote["id"],
                            dbc.Badge(quote["priority"], color=priority_color, className="ms-2"),
                            dbc.Badge(quote["status"], color=status_color, className="ms-1")
                        ]),
                        html.P([
                            html.Strong("Customer: "), quote["customer_name"]
                        ], className="mb-1"),
                        html.P([
                            html.Strong("Product: "), f"{quote['product_id']} - {quote['product_description'][:50]}..."
                        ], className="mb-1"),
                        html.P([
                            html.Strong("Location: "), quote["location"]
                        ], className="mb-1"),
                        html.P([
                            html.Strong("Quantity: "), f"{quote['quantity']} @ ${quote['unit_price']:,.2f}",
                            html.Strong(" | Total: "), f"${quote['total_price']:,.2f}"
                        ], className="mb-1"),
                        html.P([
                            html.Strong("Order Date: "), quote["order_date"].strftime('%Y-%m-%d')
                        ], className="mb-2"),
                        html.Small([
                            html.I(className="fas fa-envelope me-1"),
                            f"From: {quote['email_source']}"
                        ], className="text-muted d-block"),
                        html.Small([
                            html.I(className="fas fa-clock me-1"),
                            f"Received: {quote['email_received_at'].strftime('%Y-%m-%d %H:%M')}"
                        ], className="text-muted"),
                        # Show if quote has notes
                        html.Div([
                            html.I(className="fas fa-sticky-note me-1 text-info"),
                            html.Small("Has notes", className="text-info")
                        ], className="mt-1") if quote.get("notes") else html.Div()
                    ], width=10),
                    dbc.Col([
                        dbc.Button([
                            html.I(className="fas fa-eye")
                        ], id={"type": "select-quote", "index": quote['id']}, 
                        color="outline-primary", size="sm", title="Review Quote")
                    ], width=2, className="d-flex justify-content-end")
                ])
            ])
        ], className="mb-3")
        
        quote_cards.append(card)
    
    return quote_cards

# Server callback for quote review panel updates
@app.callback(
    Output("quote-review-panel", "children"),
    [Input("selected-quote-id", "children")]
)
def update_quote_review_panel(selected_quote_id):
    """Update the quote review panel when a quote is selected"""
    
    if not selected_quote_id:
        return html.P("Select a quote to review", className="text-muted text-center")
    
    if not db:
        return html.P("Database connection unavailable", className="text-danger")
    
    try:
        # Get the selected quote from database
        selected_quote = db.get_quote_by_id(selected_quote_id)
        
        if not selected_quote:
            return html.P("Quote not found", className="text-danger")
    except Exception as e:
        return html.P(f"Error loading quote: {str(e)}", className="text-danger")
    
    # Check if quote has existing notes
    notes_section = html.Div()
    if selected_quote.get("notes"):
        notes_history = []
        for note in selected_quote["notes"]:
            note_icon = {
                "Approval": "fas fa-check-circle text-success",
                "Denial": "fas fa-times-circle text-danger", 
                "Revision": "fas fa-edit text-warning",
                "Comment": "fas fa-comment text-info"
            }.get(note["note_type"], "fas fa-comment text-info")
            
            notes_history.append(
                html.Div([
                    html.Div([
                        html.I(className=f"{note_icon} me-1"),
                        html.Small(f"{note['note_type']} by {note['reviewer']} - {note['timestamp']}", className="text-muted")
                    ]),
                    html.P(note["content"], className="mb-1 mt-1")
                ], className="mb-2 p-2 bg-light rounded")
            )
        notes_section = html.Div([
            html.H6("Review History:", className="mb-2"),
            html.Div(notes_history, style={"max-height": "150px", "overflow-y": "auto"}),
            html.Hr()
        ])

    return html.Div([
        html.H6(f"Reviewing: {selected_quote['id']}", className="mb-3"),
        
        # Quote details summary
        dbc.Card([
            dbc.CardBody([
                html.H6("Quote Details", className="mb-2"),
                html.P([html.Strong("Customer: "), selected_quote["customer_name"]]),
                html.P([html.Strong("Product: "), f"{selected_quote['product_id']} - {selected_quote['product_description']}"]),
                html.P([html.Strong("Total: "), f"${selected_quote['total_price']:,.2f} ({selected_quote['quantity']} @ ${selected_quote['unit_price']:,.2f})"]),
                html.P([html.Strong("Expected Date: "), selected_quote["order_date"].strftime('%Y-%m-%d')]),
                dbc.Button([
                    html.I(className="fas fa-envelope me-1"),
                    "View Original Email"
                ], color="outline-info", size="sm", className="mb-2"),
                html.Small([
                    html.Strong("Subject: "), selected_quote["email_subject"]
                ], className="text-muted d-block"),
                html.Small([
                    html.Strong("Body: "), selected_quote.get("email_body", "")
                ], className="text-muted d-block")
            ])
        ], className="mb-3"),
        
        notes_section,
        
        dbc.Form([
            dbc.Row([
                dbc.Label("Priority", width=3),
                dbc.Col([
                    dcc.Dropdown(
                        id="priority-dropdown",
                        options=[
                            {"label": "High", "value": "High"},
                            {"label": "Medium", "value": "Medium"},
                            {"label": "Low", "value": "Low"}
                        ],
                        value=selected_quote["priority"]
                    )
                ], width=9)
            ], className="mb-3"),
            
            dbc.Row([
                dbc.Label("Review Notes", width=3),
                dbc.Col([
                    dbc.Textarea(
                        id="quote-review-notes",
                        placeholder="Add review comments, approval notes, or concerns...",
                        style={"height": "80px"}
                    )
                ], width=9)
            ], className="mb-3"),
            
            dbc.Row([
                dbc.Col([
                    dbc.ButtonGroup([
                        dbc.Button([
                            html.I(className="fas fa-check me-1"),
                            "Approve"
                        ], id="approve-quote-btn", color="success", size="sm", n_clicks=0),
                        dbc.Button([
                            html.I(className="fas fa-times me-1"),
                            "Deny"
                        ], id="deny-quote-btn", color="danger", size="sm", n_clicks=0),
                        dbc.Button([
                            html.I(className="fas fa-edit me-1"),
                            "Request Revision"
                        ], id="revise-quote-btn", color="warning", size="sm", n_clicks=0)
                    ], className="w-100 mb-2")
                ], width=12)
            ]),
            
            dbc.Row([
                dbc.Col([
                    dbc.Button([
                        html.I(className="fas fa-save me-1"),
                        "Update Priority & Notes"
                    ], id="update-quote-btn", color="info", size="sm", className="w-100", n_clicks=0)
                ], width=12)
            ])
        ]),
        
        html.Hr(),
        
        # Quick actions
        html.H6("Quick Actions", className="mb-2"),
        dbc.ButtonGroup([
            dbc.Button([
                html.I(className="fas fa-phone me-1"),
                "Call Customer"
            ], color="outline-primary", size="sm"),
            dbc.Button([
                html.I(className="fas fa-file-invoice me-1"),
                "Generate PDF"
            ], color="outline-info", size="sm"),
            dbc.Button([
                html.I(className="fas fa-shipping-fast me-1"),
                "Check Inventory"
            ], color="outline-secondary", size="sm")
        ], className="w-100")
    ])

# Callback for quote approval/denial actions - separate from panel updates
@app.callback(
    Output("quote-refresh", "n_intervals", allow_duplicate=True),
    [Input("approve-quote-btn", "n_clicks"),
     Input("deny-quote-btn", "n_clicks"),
     Input("revise-quote-btn", "n_clicks"),
     Input("update-quote-btn", "n_clicks")],
    [State("priority-dropdown", "value"),
     State("quote-review-notes", "value"),
     State("selected-quote-id", "children")],
    prevent_initial_call=True
)
def handle_quote_actions(approve_clicks, deny_clicks, revise_clicks, update_clicks, 
                        new_priority, notes, selected_quote_id):
    if not selected_quote_id:
        raise PreventUpdate
    
    if not db:
        print("DEBUG: No database connection")
        raise PreventUpdate
    
    try:
        ctx = callback_context
        if not ctx.triggered:
            print("DEBUG: No trigger context")
            raise PreventUpdate
        
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        triggered_value = ctx.triggered[0]['value']
        
        # Only process if button was actually clicked (n_clicks > 0)
        if not triggered_value or triggered_value == 0:
            print(f"DEBUG: Button {button_id} triggered with value {triggered_value} - ignoring")
            raise PreventUpdate
            
        reviewer = current_user  # Use the actual current user
        
        success = False
        message = ""
        
        print(f"DEBUG: Processing button click: {button_id}, clicks: {triggered_value}")
        
        if button_id == "approve-quote-btn" and approve_clicks and approve_clicks > 0:
            success = db.approve_quote(
                quote_id=selected_quote_id,
                reviewer=reviewer,
                note=notes if notes else "Quote approved for processing"
            )
            message = f"Quote {selected_quote_id} approved successfully!"
            
        elif button_id == "deny-quote-btn" and deny_clicks and deny_clicks > 0:
            if not notes:
                print("⚠️ Denial attempted without reason")
                raise PreventUpdate
            success = db.deny_quote(
                quote_id=selected_quote_id,
                reviewer=reviewer,
                reason=notes
            )
            message = f"Quote {selected_quote_id} denied."
            
        elif button_id == "revise-quote-btn" and revise_clicks and revise_clicks > 0:
            success = db.update_quote(
                quote_id=selected_quote_id,
                note=notes if notes else "Revision requested",
                note_type="Revision",
                reviewer=reviewer
            )
            message = f"Revision requested for quote {selected_quote_id}"
            
        elif button_id == "update-quote-btn" and update_clicks and update_clicks > 0:
            success = db.update_quote(
                quote_id=selected_quote_id,
                priority=new_priority,
                note=notes,
                note_type="Comment",
                reviewer=reviewer
            )
            message = f"Quote {selected_quote_id} updated successfully!"
        else:
            print(f"DEBUG: No valid action detected for button: {button_id}")
            raise PreventUpdate
        
        if success:
            # Only trigger a refresh of the quotes list
            print(f"DEBUG: Action successful, refreshing quotes list")
            return 1
        else:
            print(f"DEBUG: Action failed")
            raise PreventUpdate
            
    except Exception as e:
        print(f"DEBUG: Exception in quote actions: {str(e)}")
        raise PreventUpdate

# Separate callback for action feedback messages
@app.callback(
    Output("quote-review-panel", "children", allow_duplicate=True),
    [Input("approve-quote-btn", "n_clicks"),
     Input("deny-quote-btn", "n_clicks"), 
     Input("revise-quote-btn", "n_clicks"),
     Input("update-quote-btn", "n_clicks")],
    [State("quote-review-notes", "value"),
     State("selected-quote-id", "children"),
     State("quote-review-panel", "children")],
    prevent_initial_call=True
)
def show_action_feedback(approve_clicks, deny_clicks, revise_clicks, update_clicks,
                        notes, selected_quote_id, current_panel):
    if not selected_quote_id:
        raise PreventUpdate
        
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    triggered_value = ctx.triggered[0]['value']
    
    # Only show feedback if button was actually clicked
    if not triggered_value or triggered_value == 0:
        raise PreventUpdate
    
    # Show appropriate feedback message
    if button_id == "approve-quote-btn" and approve_clicks and approve_clicks > 0:
        feedback = dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"Quote {selected_quote_id} approved successfully!"
        ], color="success", dismissable=True, duration=4000)
    elif button_id == "deny-quote-btn" and deny_clicks and deny_clicks > 0:
        if not notes:
            feedback = dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "Please provide a reason for denial"
            ], color="warning", dismissable=True, duration=4000)
        else:
            feedback = dbc.Alert([
                html.I(className="fas fa-times-circle me-2"),
                f"Quote {selected_quote_id} denied"
            ], color="danger", dismissable=True, duration=4000)
    elif button_id == "revise-quote-btn" and revise_clicks and revise_clicks > 0:
        feedback = dbc.Alert([
            html.I(className="fas fa-edit me-2"),
            f"Revision requested for quote {selected_quote_id}"
        ], color="warning", dismissable=True, duration=4000)
    elif button_id == "update-quote-btn" and update_clicks and update_clicks > 0:
        feedback = dbc.Alert([
            html.I(className="fas fa-save me-2"),
            f"Quote {selected_quote_id} updated successfully!"
        ], color="info", dismissable=True, duration=4000)
    else:
        raise PreventUpdate
    
    # Add feedback to the current panel
    if isinstance(current_panel, list):
        return [feedback] + current_panel
    else:
        return [feedback, current_panel]

# Callback to show loading indicator when chat message is sent
@app.callback(
    [Output("chat-loading", "style"),
     Output("chat-input", "disabled"),
     Output("send-button", "disabled"),
     Output("send-icon", "className")],
    [Input("send-button", "n_clicks"),
     Input("chat-input", "n_submit")],
    [State("chat-input", "value")],
    prevent_initial_call=True
)
def show_chat_loading(send_clicks, input_submit, message):
    """Show loading indicator when processing chat message"""
    if not message or message.strip() == "":
        raise PreventUpdate
    
    # Show loading indicator and disable input
    return (
        {"display": "block"},  # Show loading
        True,                  # Disable input
        True,                  # Disable button
        "fas fa-spinner fa-spin"  # Change icon to spinner
    )

# Callback for chat functionality
@app.callback(
    [Output("chat-history", "children"),
     Output("chat-input", "value"),
     Output("chat-store", "children"),
     Output("chat-loading", "style", allow_duplicate=True),
     Output("chat-input", "disabled", allow_duplicate=True),
     Output("send-button", "disabled", allow_duplicate=True),
     Output("send-icon", "className", allow_duplicate=True)],
    [Input("send-button", "n_clicks"),
     Input("chat-input", "n_submit")],
    [State("chat-input", "value"),
     State("chat-store", "children")],
    prevent_initial_call=True
)
def update_chat(send_clicks, input_submit, message, chat_store_json):
    if not message or message.strip() == "":
        # Just return current chat history with UI reset
        chat_history = json.loads(chat_store_json)
        return (
            format_chat_history(chat_history), 
            "", 
            chat_store_json,
            {"display": "none"},      # Hide loading
            False,                    # Enable input
            False,                    # Enable button
            "fas fa-paper-plane"      # Reset icon
        )
    
    # Add user message to chat history
    chat_history = json.loads(chat_store_json)
    chat_history.append({"role": "user", "content": message})
    
    # Generate assistant response (this may take time)
    assistant_response = generate_assistant_response(message)
    chat_history.append({"role": "assistant", "content": assistant_response})
    
    # Update the chat store
    updated_chat_store = json.dumps(chat_history)
    
    # Return updated chat with loading hidden and UI re-enabled
    return (
        format_chat_history(chat_history),
        "",                       # Clear input
        updated_chat_store,
        {"display": "none"},      # Hide loading
        False,                    # Enable input
        False,                    # Enable button
        "fas fa-paper-plane"      # Reset icon
    )

def format_chat_history(chat_history):
    chat_elements = []
    
    for i, message in enumerate(chat_history):
        if message["role"] == "user":
            chat_elements.append(
                html.Div([
                    html.Div([
                        html.I(className="fas fa-user me-2"),
                        html.Strong("You")
                    ], className="mb-1"),
                    html.P(message["content"], className="mb-0")
                ], className="mb-3 p-3 bg-primary text-white rounded")
            )
        else:
            # Use Markdown component for assistant responses to render formatting
            chat_elements.append(
                html.Div([
                    html.Div([
                        html.I(className="fas fa-robot me-2 text-primary"),
                        html.Strong("Technical Assistant", className="text-primary")
                    ], className="mb-2"),
                    dcc.Markdown(
                        message["content"],
                        className="mb-0",
                        style={
                            "fontFamily": "inherit",
                            "lineHeight": "1.5"
                        }
                    )
                ], className="mb-3 p-3 bg-light rounded border-start border-primary border-3")
            )
    
    return chat_elements

def generate_assistant_response(user_message):
    """Generate an AI-powered response using Databricks foundation model with technical context."""
    
    if not ai_client:
        return "⚠️ **AI Assistant Unavailable**\n\nThe technical assistant is currently offline. Please try again later or contact support for immediate assistance."
    
    try:
        # Create a technical context prompt for field technician scenarios
        system_context = """You are an expert Manufacturing field technician assistant with deep knowledge of industrial automation, process control, and instrumentation. You specialize in troubleshooting, maintenance, and technical support.

Provide clear, actionable technical guidance based off information from AI agent.


Format your response in markdown with clear headings and bullet points."""

        # Combine context with user query
        full_prompt = f"{system_context}\n\n**Technician Question:** {user_message}\n\n**Technical Response:**"
        
        # Call Databricks foundation model
        response = ai_client.responses.create(
            model=mas_endpoint,
            input=[{
                "role": "user", 
                "content": full_prompt
            }]
        )
        
        # Extract and format the response
        if response.output and len(response.output) > 0:
            ai_response = response.output[0].content[0].text
            
            # Clean up and format the response
            formatted_response = format_ai_response(ai_response, user_message)
            return formatted_response
        else:
            return get_fallback_response(user_message)
            
    except Exception as e:
        print(f"❌ AI response error: {e}")
        return get_fallback_response(user_message)

def format_ai_response(ai_text, original_query):
    """Format AI response with proper markdown and technical structure."""
    
    # Remove any duplicate context or prompts that might be echoed back
    cleaned_text = ai_text.strip()
    
    # If the response is too short, add some structure
    if len(cleaned_text) < 50:
        return get_fallback_response(original_query)
    
    # Add header if not present
    if not cleaned_text.startswith('#') and not cleaned_text.startswith('**'):
        cleaned_text = f"## 🔧 Technical Guidance\n\n{cleaned_text}"
    
    # Ensure proper markdown formatting
    lines = cleaned_text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if line:
            # Convert numbered lists to proper markdown
            if line[0].isdigit() and '. ' in line:
                formatted_lines.append(f"{line}")
            # Convert bullet points to proper markdown
            elif line.startswith('•') or line.startswith('-'):
                if not line.startswith('- '):
                    line = f"- {line[1:].strip()}"
                formatted_lines.append(line)
            else:
                formatted_lines.append(line)
        else:
            formatted_lines.append('')
    
    return '\n'.join(formatted_lines)

def get_fallback_response(user_message):
    """Provide structured fallback responses for common technical queries."""
    
    message_lower = user_message.lower()
    
    if any(word in message_lower for word in ['valve', 'control valve', 'actuator']):
        return """## 🔧 Control Valve Troubleshooting

### **Initial Checks**
1. **Signal Verification**: Check 4-20mA control signal integrity
2. **Air Supply**: Verify pneumatic supply pressure (20-100 PSI typical)
3. **Positioner**: Inspect positioner calibration and feedback

### **Common Issues**
- **Stick-slip behavior**: Check packing friction and stem condition
- **Poor linearity**: Verify positioner tuning parameters
- **Leakage**: Inspect seat, packing, and body joints

### **Safety Notes**
⚠️ Always isolate process before maintenance
⚠️ Follow LOTO procedures
⚠️ Check for hazardous atmospheres

*Need specific model guidance? Please provide the valve tag number or model.*"""
    
    elif any(word in message_lower for word in ['pressure', 'transmitter', '3051', 'rosemount']):
        return """## 📊 Pressure Transmitter Diagnostics

### **Calibration Check**
1. **Zero point**: Verify 4mA output at zero pressure
2. **Span verification**: Check 20mA output at maximum range
3. **Linearity**: Test at 25%, 50%, 75% points

### **Common Problems**
- **Drift**: Temperature effects or sensor aging
- **Noise**: Process vibration or electrical interference  
- **Blockage**: Impulse line obstruction

### **Diagnostic Tools**
- **Hart Communicator**: For advanced diagnostics
- **Pressure calibrator**: For accuracy verification
- **Multimeter**: For signal verification

*For Rosemount 3051 series, check the diagnostic menu for self-test results.*"""
    
    elif any(word in message_lower for word in ['flow', 'flowmeter', 'magnetic', 'ultrasonic']):
        return """## 🌊 Flow Measurement Troubleshooting

### **Installation Verification**
1. **Straight pipe runs**: 10D upstream, 5D downstream minimum
2. **Grounding**: Proper electrical grounding for mag meters
3. **Orientation**: Vertical mounting for best accuracy

### **Common Issues**
- **Zero drift**: Check for coating or buildup
- **Noise**: Electrical interference or process turbulence
- **Low signal**: Conductivity issues (magnetic meters)

### **Maintenance Tasks**
- **Electrode cleaning**: For magnetic flowmeters
- **Transducer inspection**: For ultrasonic meters
- **Calibration verification**: Annual or per procedure

*Specify the flow technology (magnetic, ultrasonic, vortex) for detailed guidance.*"""
    
    else:
        return f"""## 🤖 Manufacturing Technical Assistant

I can help you with technical guidance on:

### **Equipment Types**
- 🔧 **Control Valves** - Troubleshooting, calibration, maintenance
- 📊 **Pressure Instruments** - 3051, 2051, gauge calibration  
- 🌊 **Flow Measurement** - Magnetic, ultrasonic, vortex meters
- 🌡️ **Temperature Sensors** - RTDs, thermocouples, transmitters
- ⚡ **Control Systems** - DeltaV, AMS, field devices

### **Support Areas**
- Diagnostic procedures
- Calibration steps
- Safety protocols
- Preventive maintenance
- Part identification

**Your query:** *"{user_message}"*

*Please provide more details about the specific equipment model or issue for targeted assistance.*"""

if __name__ == "__main__":
    app.run_server(debug=False, host="0.0.0.0", port=8050)
