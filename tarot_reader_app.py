#!/Library/Developer/CommandLineTools/usr/bin/python3
import sys
import importlib.util
import os
import uuid
import base64
import io
import threading
import time
from datetime import datetime
from flask import request

# Check required dependencies and provide easy pip install commands to run if needed.
_REQUIRED = {
    "dash": "pip3 install dash", # The library that provides web interface items
    "dash_bootstrap_components": "pip3 install dash-bootstrap-components", # expands on dash
    "pandas": "pip3 install pandas",
    "PIL": "pip3 install Pillow" # Library for loading images in the app
}

_missing = [(m, c) for m, c in _REQUIRED.items() if importlib.util.find_spec(m) is None]
if _missing:
    print("\nMissing packages, install these first:\n")
    for m, c in _missing:
        print(f"{c}")
    print()
    sys.exit(1)

# Put these imports further down to prevent errors if not installed yet,
# Allows you to see what you may need to install first instead of random errors.
import dash
from dash import dcc, html, Input, Output, State, callback, ALL, callback_context
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import pandas as pd
from PIL import Image

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "TarotCardImageFiles")
CSV_PATH = os.path.join(BASE_DIR, "tarot.csv") 
USERS_PATH = os.path.join(BASE_DIR, "user_list.csv")

# Color schemes for the app to use
GOLD = "#c9a84c"
PURPLE = "#9b59b6"
DARK = "#1a1025"
MID = "#2b1d3e"
CARD_BG = "#221533"
TEXT = "#f0e6d3"
DIM = "#8a7a9b"

# Style constants to provide some level of uniformity
PANEL = {"backgroundColor": MID, "borderRadius": "8px", "padding": "20px"}
GOLD_BTN = {"backgroundColor": GOLD, "color": DARK, "border": "none", "fontWeight": "bold", "borderRadius": "6px"}
PURPLE_BTN = {"backgroundColor": PURPLE, "color": "#fff", "border": "none", "fontWeight": "bold", "borderRadius": "6px"}
GREY_BTN = {"backgroundColor": "#555", "color": TEXT, "border": "none", "fontWeight": "bold", "borderRadius": "6px"}

# Data loading functions needed to populate the web apps elements
def load_card_df():
    df = pd.read_csv(CSV_PATH, dtype=str).fillna("")
    df["fileStem"] = df["cardCode"].str.strip() + "_" + df["cardName"].str.strip()
    return df

def load_users():
    if not os.path.exists(USERS_PATH):
        pd.DataFrame({"username": []}).to_csv(USERS_PATH, index=False)
        return []
    df = pd.read_csv(USERS_PATH, dtype=str)
    return df["username"].dropna().str.strip().tolist()

def save_user(username):
    df = pd.read_csv(USERS_PATH, dtype=str) if os.path.exists(USERS_PATH) else pd.DataFrame({"username": []})
    df = pd.concat([df, pd.DataFrame({"username": [username]})], ignore_index=True)
    df.to_csv(USERS_PATH, index=False)

def build_card_list():
    card_df = load_card_df()
    
    image_files = {}
    if os.path.exists(IMAGE_DIR):
        for f in os.listdir(IMAGE_DIR):
            if f.lower().endswith('.jpg'):
                stem = os.path.splitext(f)[0]
                image_files[stem] = os.path.join(IMAGE_DIR, f)
    
    # Match cards with images based on parts of the file name
    cards = []
    for _, row in card_df.iterrows():
        stem = row["fileStem"]
        if stem in image_files:
            cards.append({
                "stem": stem,
                "path": image_files[stem],
                "data": row.to_dict()
            })
    
    return cards

def img_to_base64(image_path, max_width=300):
    try:
        img = Image.open(image_path).convert("RGB")
        # Resize while maintaining and aspet ratio that makes sense
        aspect_ratio = img.height / img.width
        new_height = int(max_width * aspect_ratio)
        img = img.resize((max_width, new_height))
        
        # Convert to base64 string for compressing
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{img_str}"
    except:
        return ""

# Initialize data
CARD_DATA = build_card_list()

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG], suppress_callback_exceptions=True)
app.title = "✦ Tarot Card Reader"

# Add shutdown functionality
def shutdown_server():
    def shutdown():
        time.sleep(1)  # Give the response time to send
        os._exit(0)  # Force exit the application, needed to prevent attempted dups on same port
    
    thread = threading.Thread(target=shutdown)
    thread.start()
    return "Server shutting down"

# Shutdown endpoint for Flask Server
@app.server.route('/shutdown', methods=['POST'])
def shutdown():
    return shutdown_server()

# App layout
app.layout = dbc.Container(
    fluid=True,
    style={"backgroundColor": DARK, "minHeight": "100vh", "color": TEXT, "fontFamily": "Georgia, serif"},
    children=[
        # Data stores to manage user and session data
        dcc.Store(id="selected-user", data=""),
        dcc.Store(id="session-id", data=""),
        dcc.Store(id="current-card-index", data=0),
        dcc.Store(id="reading-results", data=[]),
        dcc.Store(id="app-screen", data="user-selection"),  # user-selection, card-browser, reading-summary
        
        # Header Ele,ents
        dbc.Row([
            dbc.Col(
                html.H2("✦ Tarot Card Reader ✦", 
                       style={"color": GOLD, "textAlign": "center", "paddingTop": "20px", "letterSpacing": "3px"}),
                md=10
            ),
            dbc.Col([
                dbc.Button(
                    "Stop Server",
                    id="shutdown-btn",
                    style={"backgroundColor": "#e74c3c", "color": "white", "border": "none", 
                          "borderRadius": "6px", "fontWeight": "bold", "marginTop": "25px"},
                    size="sm"
                )
            ], md=2, className="text-end")
        ]),
        html.Hr(style={"borderColor": GOLD}),
        
        # Main content area
        html.Div(id="main-content", style={"padding": "20px"}),
        
        # Components for callback IDs to map the buttons to
        html.Div([
            dbc.Button("", id="main-shutdown-btn", style={"display": "none"}),
            dbc.Input(id="new-user-input", style={"display": "none"}),
            dbc.Button("", id="add-user-btn", style={"display": "none"}),
            html.Div(id="add-user-feedback", style={"display": "none"}),
            dbc.Button("", id="prev-card", style={"display": "none"}),
            dbc.Button("", id="next-card", style={"display": "none"}),
            html.Div([dcc.Slider(id="card-slider", min=0, max=1, value=0)], style={"display": "none"}),
            dbc.Button("", id="face-up-btn", style={"display": "none"}),
            dbc.Button("", id="face-down-btn", style={"display": "none"}),
            dbc.Button("", id="back-to-users", style={"display": "none"}),
            dbc.Button("", id="view-summary", style={"display": "none"}),
            dbc.Button("", id="add-more-cards", style={"display": "none"}),
            dbc.Button("", id="new-reading", style={"display": "none"}),
            dbc.Button("", id="select-another-card", style={"display": "none"}),
        ], style={"display": "none"})
    ]
)

# User selection screen
def user_selection_screen():
    users = load_users()
    
    user_buttons = []
    for i, user in enumerate(users):
        user_buttons.append(
            dbc.Button(
                f"Select {user}",
                id={"type": "select-user", "index": i},
                style={**GOLD_BTN, "width": "100%", "margin": "5px 0"},
                size="lg"
            )
        )
    
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H4("Select User", style={"color": TEXT, "marginBottom": "20px"}),
                    html.Div(user_buttons if users else html.P("No users found. Add one below.", style={"color": DIM}))
                ], style=PANEL)
            ], md=6),
            
            dbc.Col([
                html.Div([
                    html.H4("Add New User", style={"color": TEXT, "marginBottom": "20px"}),
                    dbc.Input(
                        id="new-user-input",
                        placeholder="Enter username...",
                        style={"backgroundColor": CARD_BG, "color": TEXT, "border": f"1px solid {GOLD}", "marginBottom": "10px"}
                    ),
                    dbc.Button("Add User", id="add-user-btn", style={**PURPLE_BTN, "width": "100%"}),
                    html.Div(id="add-user-feedback", style={"marginTop": "10px"})
                ], style=PANEL)
            ], md=6)
        ]),
        
        # Server control section
        html.Hr(style={"borderColor": GOLD, "margin": "30px 0"}),
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.H6("Server Control", style={"color": DIM, "marginBottom": "15px"}),
                    html.P("Click below to safely shutdown the server when you're done.", 
                          style={"color": TEXT, "fontSize": "14px", "marginBottom": "15px"}),
                    dbc.Button(
                        "⏹️ Stop Server",
                        id="main-shutdown-btn", 
                        style={"backgroundColor": "#e74c3c", "color": "white", "border": "none", 
                              "borderRadius": "6px", "fontWeight": "bold", "padding": "10px 20px"},
                        size="lg"
                    )
                ], style=PANEL)
            ], md=12)
        ])
    ])

# Card browser screen
def card_browser_screen(current_index, username, session_id, readings):
    if not CARD_DATA:
        return html.Div("No cards available", style={"color": TEXT})
    
    current_card = CARD_DATA[current_index]
    card_data = current_card["data"]
    img_src = img_to_base64(current_card["path"], max_width=250)
    
    # Create thumbnail strip (show 7 cards around current)
    thumbnails = []
    start_idx = max(0, current_index - 3)
    end_idx = min(len(CARD_DATA), current_index + 4)
    
    for i in range(start_idx, end_idx):
        card = CARD_DATA[i]
        thumb_src = img_to_base64(card["path"], max_width=80)
        is_selected = (i == current_index)
        
        thumbnails.append(
            html.Div([
                html.Img(
                    src=thumb_src,
                    style={
                        "width": "60px",
                        "height": "auto",
                        "borderRadius": "4px",
                        "border": f"2px solid {GOLD}" if is_selected else "2px solid transparent",
                        "cursor": "pointer",
                        "margin": "2px"
                    }
                ),
                html.P(card["data"]["cardName"][:15], 
                      style={"fontSize": "10px", "color": GOLD if is_selected else DIM, "textAlign": "center"})
            ],
            id={"type": "card-thumb", "index": i},
            style={"display": "inline-block", "margin": "5px", "textAlign": "center"}
            )
        )
    
    return html.Div([
        # Header with user info
        dbc.Row([
            dbc.Col(html.H4("Select Your Cards", style={"color": GOLD}), md=8),
            dbc.Col(html.P(f"User: {username} | Session: {session_id[:8]}...", 
                          style={"color": DIM, "textAlign": "right"}), md=4)
        ], className="mb-3"),
        
        dbc.Row([
            # Main card display
            dbc.Col([
                html.Div([
                    # Navigation buttons and main card
                    dbc.Row([
                        dbc.Col(
                            dbc.Button("◀", id="prev-card", style={**GOLD_BTN, "fontSize": "20px"}),
                            width="auto", className="d-flex align-items-center"
                        ),
                        dbc.Col(
                            html.Img(src=img_src, style={"width": "100%", "maxWidth": "250px", "borderRadius": "8px"}),
                            className="text-center"
                        ),
                        dbc.Col(
                            dbc.Button("▶", id="next-card", style={**GOLD_BTN, "fontSize": "20px"}),
                            width="auto", className="d-flex align-items-center"
                        )
                    ], align="center", justify="center"),
                    
                    # Card info
                    html.H5(card_data["cardName"], style={"color": GOLD, "textAlign": "center", "margin": "15px 0"}),
                    html.P(f"Card {current_index + 1} of {len(CARD_DATA)}", 
                          style={"color": DIM, "textAlign": "center"}),
                    
                    # Card slider to allow users to scroll through cards more quickly
                    dcc.Slider(
                        id="card-slider",
                        min=0,
                        max=len(CARD_DATA) - 1,
                        step=1,
                        value=current_index,
                        marks=None,
                        tooltip={"always_visible": False}
                    ),
                    
                    # Orientation buttons
                    html.Hr(style={"borderColor": GOLD, "margin": "20px 0"}),
                    html.H6("How was this card drawn?", style={"color": TEXT, "textAlign": "center"}),
                    dbc.Row([
                        dbc.Col(
                            dbc.Button("Face Up ☀", id="face-up-btn", style={**GOLD_BTN, "width": "100%", "padding": "10px"}),
                            md=6
                        ),
                        dbc.Col(
                            dbc.Button("Face Down 🌙", id="face-down-btn", style={**PURPLE_BTN, "width": "100%", "padding": "10px"}),
                            md=6
                        )
                    ])
                ], style=PANEL)
            ], md=6),
            
            # Card details and thumbnails
            dbc.Col([
                html.Div([
                    html.H6("Browse Cards", style={"color": TEXT, "marginBottom": "10px"}),
                    html.Div(thumbnails, style={"overflowX": "auto", "whiteSpace": "nowrap", "padding": "10px", 
                                               "backgroundColor": MID, "borderRadius": "6px"})
                ], style={"marginBottom": "20px"}),
                
                # Card descriptions
                html.Div([
                    html.H6("Card Meanings", style={"color": GOLD, "marginBottom": "15px", "fontWeight": "bold"}),
                    
                    # Face Up section
                    html.Div([
                        html.H6("☀ Face Up (Upright)", style={"color": GOLD, "fontWeight": "bold", "marginBottom": "8px"}),
                        html.P(card_data.get("upScript", "No description available"), 
                              style={"color": TEXT, "fontSize": "15px", "lineHeight": "1.5", 
                                    "marginBottom": "20px", "padding": "10px", 
                                    "backgroundColor": CARD_BG, "borderRadius": "6px",
                                    "borderLeft": f"4px solid {GOLD}"})
                    ], style={"marginBottom": "15px"}),
                    
                    # Face Down section  
                    html.Div([
                        html.H6("🌙 Face Down (Reversed)", style={"color": PURPLE, "fontWeight": "bold", "marginBottom": "8px"}),
                        html.P(card_data.get("rxScript", "No description available"), 
                              style={"color": TEXT, "fontSize": "15px", "lineHeight": "1.5",
                                    "marginBottom": "10px", "padding": "10px",
                                    "backgroundColor": CARD_BG, "borderRadius": "6px", 
                                    "borderLeft": f"4px solid {PURPLE}"})
                    ]),
                    
                    # Card details
                    html.Hr(style={"borderColor": MID, "margin": "15px 0"}),
                    html.Div([
                        html.P(f"Suit: {card_data.get('suit', 'N/A')}", 
                              style={"color": DIM, "fontSize": "12px", "margin": "2px 0"}),
                        html.P(f"Element: {card_data.get('element', 'N/A')}", 
                              style={"color": DIM, "fontSize": "12px", "margin": "2px 0"}),
                        html.P(f"Arcana: {card_data.get('arcanaType', 'N/A')}", 
                              style={"color": DIM, "fontSize": "12px", "margin": "2px 0"})
                    ])
                ], style=PANEL)
            ], md=6)
        ]),
        
        # Footer buttons
        html.Hr(style={"borderColor": GOLD, "margin": "20px 0"}),
        dbc.Row([
            dbc.Col(
                dbc.Button("◀ Back to Users", id="back-to-users", style={**PURPLE_BTN, "padding": "8px 20px"}),
                width="auto"
            ),
            dbc.Col(
                dbc.Button("View Reading Summary", id="view-summary", style={**GOLD_BTN, "padding": "8px 20px"}),
                width="auto"
            ) if readings else None
        ])
    ])

# Reading summary screen
def reading_summary_screen(username, session_id, readings):
    if not readings:
        return html.Div([
            html.H4("No cards selected yet", style={"color": TEXT}),
            dbc.Button("Start Reading", id="start-reading", style={**GOLD_BTN, "margin": "20px 0"})
        ])
    
    # Create reading table
    reading_rows = []
    for i, reading in enumerate(readings):
        reading_rows.append(
            html.Tr([
                html.Td(f"{i+1}", style={"color": DIM}),
                html.Td(reading["cardName"], style={"color": GOLD}),
                html.Td(reading["orientation"], style={"color": GOLD if reading["orientation"] == "Face Up" else PURPLE}),
                html.Td(reading["script"][:100] + "..." if len(reading["script"]) > 100 else reading["script"], 
                       style={"color": TEXT, "fontSize": "12px"}),
                html.Td(reading["timestamp"], style={"color": DIM, "fontSize": "11px"})
            ])
        )
    
    return html.Div([
        html.H4("✦ Reading Summary", style={"color": GOLD, "marginBottom": "10px"}),
        html.P(f"Reader: {username} | Session: {session_id[:8]}... | Cards: {len(readings)}", 
              style={"color": DIM, "marginBottom": "20px"}),
        
        # Reading table
        html.Div([
            dbc.Table(
                [
                    html.Thead(html.Tr([
                        html.Th("#", style={"color": GOLD}),
                        html.Th("Card", style={"color": GOLD}),
                        html.Th("Orientation", style={"color": GOLD}),
                        html.Th("Description", style={"color": GOLD}),
                        html.Th("Time", style={"color": GOLD})
                    ])),
                    html.Tbody(reading_rows)
                ],
                bordered=False,
                hover=True,
                size="sm",
                style={"color": TEXT}
            )
        ], style={"backgroundColor": CARD_BG, "borderRadius": "8px", "padding": "15px", "marginBottom": "20px"}),
        
        # Action buttons
        dbc.Row([
            dbc.Col(
                dbc.Button("Add More Cards", id="add-more-cards", style={**GOLD_BTN, "padding": "10px 20px"}),
                width="auto"
            ),
            dbc.Col(
                dbc.Button("New Reading", id="new-reading", style={**PURPLE_BTN, "padding": "10px 20px"}),
                width="auto"
            )
        ])
    ])

# Card logged confirmation screen
def card_logged_screen(username, session_id, readings, current_card_index):
    if not readings:
        return reading_summary_screen(username, session_id, readings)
    
    # Get the most recently logged card
    latest_reading = readings[-1]
    current_card = CARD_DATA[current_card_index or 0]
    
    orientation_color = GOLD if latest_reading["orientation"] == "Face Up" else PURPLE
    
    # Create image (rotated if face down)
    if latest_reading["orientation"] == "Face Up":
        img_src = img_to_base64(current_card["path"], max_width=200)
    else:
        # For face down, we could rotate the image or show it normally
        img_src = img_to_base64(current_card["path"], max_width=200)
    
    return html.Div([
        html.H4("✦ Card Logged Successfully", style={"color": GOLD, "marginBottom": "20px"}),
        
        dbc.Row([
            # Card image and info
            dbc.Col([
                html.Img(src=img_src, style={
                    "width": "100%", 
                    "maxWidth": "200px", 
                    "borderRadius": "10px",
                    "boxShadow": f"0 0 20px {orientation_color}66"
                }),
                html.H5(latest_reading["cardName"], 
                       style={"color": GOLD, "textAlign": "center", "marginTop": "15px"}),
                html.P(f"{latest_reading['orientation']}", 
                      style={"color": orientation_color, "textAlign": "center", "fontSize": "18px", "fontWeight": "bold"})
            ], md=4, className="text-center"),
            
            # Reading description
            dbc.Col([
                html.Div([
                    html.H5(f"{'✦ Upright Reading' if latest_reading['orientation'] == 'Face Up' else '✦ Reversed Reading'}", 
                           style={"color": orientation_color, "marginBottom": "15px"}),
                    
                    html.Div([
                        html.P(latest_reading["script"], 
                              style={"color": TEXT, "fontSize": "16px", "lineHeight": "1.6",
                                    "padding": "15px", "backgroundColor": CARD_BG,
                                    "borderRadius": "8px", "borderLeft": f"4px solid {orientation_color}",
                                    "marginBottom": "15px"})
                    ]),
                    
                    html.Hr(style={"borderColor": MID, "margin": "20px 0"}),
                    
                    html.Div([
                        html.P(f"Reader: {username}", style={"color": TEXT, "fontSize": "14px", "margin": "5px 0"}),
                        html.P(f"Session: {session_id[:8]}...", style={"color": DIM, "fontSize": "12px", "margin": "5px 0"}),
                        html.P(f"Total Cards: {len(readings)}", style={"color": GOLD, "fontSize": "14px", "margin": "5px 0"}),
                        html.P(f"Suit: {latest_reading.get('suit', 'N/A')} | Element: {latest_reading.get('element', 'N/A')}", 
                              style={"color": DIM, "fontSize": "12px", "margin": "5px 0"})
                    ])
                ], style=PANEL)
            ], md=8)
        ], className="mb-4"),
        
        # Action buttons
        html.Div([
            html.H6("What would you like to do next?", style={"color": TEXT, "marginBottom": "20px"}),
            dbc.Row([
                dbc.Col([
                    dbc.Button("Select Another Card", id="select-another-card", 
                             style={**GOLD_BTN, "width": "100%", "padding": "12px"})
                ], md=4),
                dbc.Col([
                    dbc.Button("View Full Reading", id="view-summary", 
                             style={**PURPLE_BTN, "width": "100%", "padding": "12px"})
                ], md=4),
                dbc.Col([
                    dbc.Button("Start New Reading", id="new-reading", 
                             style={**GREY_BTN, "width": "100%", "padding": "12px"})
                ], md=4)
            ])
        ])
    ])

# Main content router
@app.callback(
    Output("main-content", "children"),
    [Input("app-screen", "data"),
     Input("current-card-index", "data"),
     Input("selected-user", "data"),
     Input("session-id", "data"),
     Input("reading-results", "data")]
)
def display_screen(screen, card_index, username, session_id, readings):
    screen = screen or "user-selection"
    
    if screen == "card-browser":
        return card_browser_screen(card_index or 0, username or "", session_id or "", readings or [])
    elif screen == "reading-summary":
        return reading_summary_screen(username or "", session_id or "", readings or [])
    elif screen == "card-logged":
        return card_logged_screen(username or "", session_id or "", readings or [], card_index or 0)
    else:
        return user_selection_screen()

# User selection callbacks
@app.callback(
    [Output("selected-user", "data"),
     Output("session-id", "data"), 
     Output("app-screen", "data")],
    [Input({"type": "select-user", "index": ALL}, "n_clicks")],
    [State("selected-user", "data"),
     State("session-id", "data")],
    prevent_initial_call=True
)
def select_user(n_clicks_list, current_user, current_session):
    if not any(n_clicks_list):
        return current_user, current_session, "user-selection"
    
    # Find which button was clicked
    ctx = callback_context
    if not ctx.triggered:
        return current_user, current_session, "user-selection"
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    button_index = eval(button_id)["index"]
    
    users = load_users()
    if button_index < len(users):
        selected_user = users[button_index]
        new_session_id = str(uuid.uuid4())
        return selected_user, new_session_id, "card-browser"
    
    return current_user, current_session, "user-selection"

# Add user callback
@app.callback(
    [Output("add-user-feedback", "children"),
     Output("new-user-input", "value")],
    [Input("add-user-btn", "n_clicks")],
    [State("new-user-input", "value")],
    prevent_initial_call=True
)
def add_user(n_clicks, username):
    if not n_clicks or not username or not username.strip():
        return "", ""
    
    username = username.strip()
    users = load_users()
    
    if username in users:
        return dbc.Alert("User already exists!", color="warning", duration=3000), username
    
    try:
        save_user(username)
        return dbc.Alert("User added successfully!", color="success", duration=3000), ""
    except Exception as e:
        return dbc.Alert(f"Error adding user: {str(e)}", color="danger", duration=3000), username

# Card navigation callbacks

# Previous card
@app.callback(
    Output("current-card-index", "data", allow_duplicate=True),
    [Input("prev-card", "n_clicks")],
    [State("current-card-index", "data")],
    prevent_initial_call=True
)
def go_to_previous_card(n_clicks, current_index):
    if n_clicks and n_clicks > 0:
        return max(0, (current_index or 0) - 1)
    raise PreventUpdate

# Next card
@app.callback(
    Output("current-card-index", "data", allow_duplicate=True),
    [Input("next-card", "n_clicks")],
    [State("current-card-index", "data")],
    prevent_initial_call=True
)
def go_to_next_card(n_clicks, current_index):
    if n_clicks and n_clicks > 0:
        return min(len(CARD_DATA) - 1, (current_index or 0) + 1)
    raise PreventUpdate

# Slider navigation
@app.callback(
    Output("current-card-index", "data", allow_duplicate=True),
    [Input("card-slider", "value")],
    prevent_initial_call=True
)
def navigate_with_slider(slider_value):
    if slider_value is not None:
        return min(max(0, slider_value), len(CARD_DATA) - 1)
    raise PreventUpdate

# Thumbnail navigation
@app.callback(
    Output("current-card-index", "data", allow_duplicate=True),
    [Input({"type": "card-thumb", "index": ALL}, "n_clicks")],
    [State("current-card-index", "data")],
    prevent_initial_call=True
)
def navigate_with_thumbnails(thumb_clicks, current_index):
    ctx = callback_context
    if not ctx.triggered or not any(thumb_clicks or []):
        raise PreventUpdate
    
    trigger_id = ctx.triggered[0]["prop_id"]
    if "card-thumb" in trigger_id:
        # Extract index from the trigger ID
        import json
        button_info = json.loads(trigger_id.split('.')[0])
        thumb_index = button_info["index"]
        return thumb_index
    
    raise PreventUpdate

# Card selection callbacks (Face Up/Face Down)
@app.callback(
    [Output("reading-results", "data"),
     Output("app-screen", "data", allow_duplicate=True)],
    [Input("face-up-btn", "n_clicks"),
     Input("face-down-btn", "n_clicks")],
    [State("current-card-index", "data"),
     State("selected-user", "data"),
     State("session-id", "data"),
     State("reading-results", "data")],
    prevent_initial_call=True
)
def log_card_selection(face_up_clicks, face_down_clicks, card_index, username, session_id, current_readings):
    ctx = callback_context
    if not ctx.triggered:
        return current_readings or [], "card-browser"
    
    trigger_id = ctx.triggered[0]["prop_id"]
    
    if not any([face_up_clicks, face_down_clicks]) or not CARD_DATA:
        return current_readings or [], "card-browser"
    
    current_card = CARD_DATA[card_index or 0]
    card_data = current_card["data"]
    
    orientation = "Face Up" if "face-up-btn" in trigger_id else "Face Down"
    script = card_data.get("upScript" if orientation == "Face Up" else "rxScript", "")
    
    new_reading = {
        "sessionId": session_id,
        "username": username,
        "cardName": card_data["cardName"],
        "cardCode": card_data["cardCode"],
        "orientation": orientation,
        "script": script,
        "suit": card_data.get("suit", ""),
        "element": card_data.get("element", ""),
        "arcanaType": card_data.get("arcanaType", ""),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    readings = (current_readings or []).copy()
    readings.append(new_reading)
    
    # Add logic to save readings to a CSV or database if needed

    # Go to card log screen to show confirmation and next options
    return readings, "card-logged"

# Back to users callback
@app.callback(
    [Output("app-screen", "data", allow_duplicate=True),
     Output("reading-results", "data", allow_duplicate=True)],
    [Input("back-to-users", "n_clicks")],
    [State("reading-results", "data")],
    prevent_initial_call=True
)
def go_back_to_users(n_clicks, current_readings):
    if n_clicks and n_clicks > 0:
        return "user-selection", current_readings or []
    raise PreventUpdate

# View summary callback
@app.callback(
    Output("app-screen", "data", allow_duplicate=True),
    [Input("view-summary", "n_clicks")],
    prevent_initial_call=True
)
def go_to_summary(n_clicks):
    if n_clicks and n_clicks > 0:
        return "reading-summary"
    raise PreventUpdate

# Add more cards callback
@app.callback(
    Output("app-screen", "data", allow_duplicate=True),
    [Input("add-more-cards", "n_clicks")],
    prevent_initial_call=True
)
def add_more_cards(n_clicks):
    if n_clicks and n_clicks > 0:
        return "card-browser"
    raise PreventUpdate

# Select another card callback
@app.callback(
    Output("app-screen", "data", allow_duplicate=True),
    [Input("select-another-card", "n_clicks")],
    prevent_initial_call=True
)
def select_another_card(n_clicks):
    if n_clicks and n_clicks > 0:
        return "card-browser"
    raise PreventUpdate

# New reading callback 
@app.callback(
    [Output("app-screen", "data", allow_duplicate=True),
     Output("reading-results", "data", allow_duplicate=True)],
    [Input("new-reading", "n_clicks")],
    prevent_initial_call=True
)
def start_new_reading(n_clicks):
    if n_clicks and n_clicks > 0:
        return "user-selection", []
    raise PreventUpdate

# Add clientside callback for shutdown
# The below callback was created mostly by AI as I struggled to get the app to gracefully shut down.
app.clientside_callback(
    """
    function(header_clicks, main_clicks) {
        var total_clicks = (header_clicks || 0) + (main_clicks || 0);
        if (total_clicks > 0) {
            var confirmed = confirm('Are you sure you want to stop the server?\\n\\nThis will close the application.');
            if (confirmed) {
                fetch('/shutdown', {
                    method: 'POST'
                }).then(function(response) {
                    alert('Server is shutting down. You can close this tab.');
                    setTimeout(function() { 
                        try { window.close(); } catch(e) { }
                    }, 1000);
                }).catch(function(error) {
                    alert('Server is shutting down. You can close this tab.');
                    setTimeout(function() { 
                        try { window.close(); } catch(e) { }
                    }, 1000);
                });
            }
        }
        return {};
    }
    """,
    Output("shutdown-btn", "style"),
    [Input("shutdown-btn", "n_clicks"),
     Input("main-shutdown-btn", "n_clicks")],
    prevent_initial_call=True
)

if __name__ == "__main__":
    print("Starting Tarot Card Reader")
    print("Open your browser to: http://127.0.0.1:8050")
    app.run(debug=True, host="127.0.0.1", port=8050)