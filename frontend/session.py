"""
frontend/session.py — Session Management.

Wraps Streamlit's untyped session state to provide structured access
to the ApplicationState.
"""

import streamlit as st

from frontend.state import ApplicationState


def init_session() -> None:
    """Initialize the global application state if it doesn't exist."""
    if "app_state" not in st.session_state:
        st.session_state.app_state = ApplicationState()


def get_state() -> ApplicationState:
    """Retrieve the current ApplicationState."""
    init_session()
    return st.session_state.app_state


def set_active_workspace(workspace_id: str) -> None:
    """Safely update the active workspace."""
    state = get_state()
    state.active_workspace_id = workspace_id


def set_selected_player(player_id: int | None) -> None:
    """Safely update the selected player."""
    state = get_state()
    state.selected_player_id = player_id


def set_selected_team(team_id: int | None) -> None:
    """Safely update the selected team."""
    state = get_state()
    state.selected_team_id = team_id
