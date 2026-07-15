"""
# ruff: noqa: E402
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

# Workspace imports
import frontend.pages.dashboard as dashboard  # noqa: E402
import frontend.pages.player_intelligence as player_intelligence  # noqa: E402
import frontend.pages.recruitment_intelligence as recruitment_intelligence  # noqa: E402
import frontend.pages.team_intelligence as team_intelligence  # noqa: E402
from frontend.components.ask_athena import render_ask_athena_drawer  # noqa: E402
from frontend.components.states import render_empty_state  # noqa: E402
from frontend.layout import render_page_header  # noqa: E402
from frontend.session import get_state, init_session  # noqa: E402
from frontend.sidebar import render_global_sidebar  # noqa: E402
from frontend.theme import load_theme  # noqa: E402
from shared.config.navigation import get_workspace_by_id  # noqa: E402

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
        render_empty_state(
            "⚠",
            "Workspace Not Found",
            "The requested workspace does not exist in the configuration.",
        )
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
            suggestion="Select another workspace to continue your analysis.",
        )
    else:
        # Fallback for future workspaces
        render_page_header(active_ws.name, active_ws.question, active_ws.icon)
        render_empty_state(
            icon=active_ws.icon,
            title=f"{active_ws.name} Workspace",
            description="This workspace is currently under construction.",
            suggestion="Use the sidebar to navigate to a different workspace.",
        )

# Render Contextual Drawer
with athena_col:
    render_ask_athena_drawer()
