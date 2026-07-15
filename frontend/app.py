"""
frontend/app.py — Athena Streamlit application entry point.

This is the main application shell. Run with:
    streamlit run frontend/app.py

It delegates styling, state management, and navigation to their respective modules,
and routes to the active workspace.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Path setup — allow imports from project root
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from frontend.session import init_session, get_state
from frontend.theme import load_theme
from frontend.sidebar import render_global_sidebar
from frontend.layout import render_page_header
from frontend.components.states import render_empty_state
from frontend.components.ask_athena import render_ask_athena_drawer
from shared.config.navigation import get_workspace_by_id

# Workspace imports
import frontend.pages.dashboard as dashboard
import frontend.pages.player_intelligence as player_intelligence
import frontend.pages.team_intelligence as team_intelligence
import frontend.pages.recruitment_intelligence as recruitment_intelligence


# ─────────────────────────────────────────────────────────────────────────────
# Application Initialization
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Athena — Football Decision Intelligence",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 1. Initialize State
init_session()
state = get_state()

# 2. Inject Enterprise Theme
load_theme()

# 3. Render Global Chrome (Navigation & Selectors)
render_global_sidebar()


# ─────────────────────────────────────────────────────────────────────────────
# Main Layout & Routing
# ─────────────────────────────────────────────────────────────────────────────

# Create a master layout: 3/4 Main Content, 1/4 Ask Athena Drawer
main_col, athena_col = st.columns([3, 1], gap="large")

with main_col:
    active_ws = get_workspace_by_id(state.active_workspace_id)
    
    if not active_ws:
        render_page_header("Error", "Invalid Workspace")
        render_empty_state("⚠", "Workspace Not Found", "The requested workspace does not exist in the configuration.")
    elif state.active_workspace_id == "dashboard":
        dashboard.render()
    elif state.active_workspace_id == "player_intelligence":
        player_intelligence.render()
    elif state.active_workspace_id == "team_intelligence":
        team_intelligence.render()
    elif state.active_workspace_id == "recruitment":
        recruitment_intelligence.render()
    elif state.active_workspace_id == "ask_athena":
        # The user clicked Ask Athena in the navigation.
        # Since Ask Athena is a persistent drawer, we can show a placeholder or
        # default to dashboard for the main view and highlight the drawer.
        render_empty_state(
            icon="◇",
            title="Ask Athena",
            description="Athena is integrated directly into your workflow. Use the contextual drawer on the right to interact with her at any time.",
            suggestion="Select another workspace to continue your analysis."
        )
    else:
        # Fallback for future workspaces
        render_page_header(active_ws.name, active_ws.question, active_ws.icon)
        render_empty_state(
            icon=active_ws.icon,
            title=f"{active_ws.name} Workspace",
            description=f"This workspace is currently under construction.",
            suggestion="Use the sidebar to navigate to a different workspace."
        )

# Render Contextual Drawer
with athena_col:
    render_ask_athena_drawer()
