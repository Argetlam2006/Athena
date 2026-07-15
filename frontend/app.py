"""
frontend/app.py — Athena Streamlit application entry point.

This is the main application shell. Run with:
    streamlit run frontend/app.py
    make app

It delegates styling, state management, and navigation to their respective modules,
acting purely as the orchestrator.
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
# Routing & Active Workspace Render
# ─────────────────────────────────────────────────────────────────────────────

# In Phase 5, we only render the application shell and placeholders.
# The actual workspace pages (e.g. dashboard.py) will be implemented in future phases.

active_ws = get_workspace_by_id(state.active_workspace_id)

if active_ws:
    render_page_header(
        title=active_ws.name,
        subtitle=active_ws.question,
        icon=active_ws.icon
    )
    
    # Placeholder content
    render_empty_state(
        icon=active_ws.icon,
        title=f"{active_ws.name} Workspace",
        description=f"This workspace is currently under construction. Future updates will bring: {active_ws.description}.",
        suggestion="Use the sidebar to navigate to a different workspace."
    )
    
    # Global context debug view
    st.markdown("<div style='margin-top: 3rem;'></div>", unsafe_allow_html=True)
    with st.expander("System State Debug"):
        st.json({
            "active_workspace": state.active_workspace_id,
            "selected_player_id": state.selected_player_id,
            "selected_team_id": state.selected_team_id
        })

else:
    # Fallback
    render_page_header("Error", "Invalid Workspace")
    render_empty_state("⚠", "Workspace Not Found", "The requested workspace does not exist in the configuration.")

# Optional drawer test (Ask Athena)
if state.active_workspace_id == "ask_athena":
    render_ask_athena_drawer()
