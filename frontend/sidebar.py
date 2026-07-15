"""
frontend/sidebar.py — Global persistent sidebar.

Renders navigation, context selectors, system status, and the Ask Athena placeholder.
Directly reads from and writes to the centralized session state.
"""

import streamlit as st
import pandas as pd

from frontend.data.players import get_player_index
from frontend.data.teams import get_team_index
from frontend.session import (
    get_state,
    set_active_workspace,
    set_selected_player,
    set_selected_team,
)
from shared.config.navigation import WORKSPACES


def render_workspace_navigation() -> None:
    """Renders dynamic workspace links based on config."""
    state = get_state()

    st.markdown(
        "<div style='margin-bottom: 1rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>Intelligence Workspaces</div>",
        unsafe_allow_html=True,
    )

    for workspace in WORKSPACES:
        if workspace.status == "live":
            is_active = state.active_workspace_id == workspace.id
            btn_key = f"nav_{workspace.id}"

            if is_active:
                st.markdown(f"**{workspace.icon} {workspace.name}**")
            else:
                if st.button(
                    f"{workspace.icon} {workspace.name}",
                    key=btn_key,
                    use_container_width=True,
                ):
                    set_active_workspace(workspace.id)
                    st.rerun()


def render_context_selectors() -> None:
    """Renders global player and team selectors."""
    st.markdown(
        "<div style='margin-top: 2rem; margin-bottom: 1rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>Global Context</div>",
        unsafe_allow_html=True,
    )

    # 1. Player Search & Selection (Metadata Index)
    df_players = get_player_index()
    if not df_players.empty:
        search_term = st.text_input("Search Player", placeholder="e.g. Rodri")
        
        # Filter metadata dynamically using multi-term matching
        if search_term:
            terms = search_term.lower().split()
            mask = pd.Series(True, index=df_players.index)
            for term in terms:
                mask &= df_players["normalized_name"].str.contains(term, na=False)
            matches = df_players[mask].head(50)
        else:
            matches = df_players.nlargest(20, "minutes_played")
            
        player_options = {"None": None}
        for _, row in matches.iterrows():
            player_options[f"{row['player_name']} ({row['team_name']})"] = row['player_id']
            
        selected_player_name = st.selectbox(
            "Select Focus Player",
            options=list(player_options.keys()),
            index=0,
            help="Select a player to focus all workspaces on."
        )
        set_selected_player(player_options[selected_player_name])
    else:
        st.selectbox("Focus Player", ["Data not loaded"])

    # 2. Team Selection (Metadata Index)
    df_teams = get_team_index()
    team_options = {"None": None}
    if not df_teams.empty:
        df_teams = df_teams.sort_values("team_name")
        for _, row in df_teams.iterrows():
            team_options[row["team_name"]] = row["team_id"]
            
    selected_team_name = st.selectbox(
        "Focus Team",
        options=list(team_options.keys()),
        index=0,
        help="Select a team to focus all workspaces on."
    )
    set_selected_team(team_options[selected_team_name])


def render_system_status() -> None:
    """Renders the system status indicator."""
    st.markdown(
        "<div style='margin-top: 2rem; margin-bottom: 0.5rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>System Status</div>",
        unsafe_allow_html=True,
    )

    # Mocking status check
    st.markdown(
        """
    <div style="font-size: 0.8rem; color: #10b981; display: flex; align-items: center; gap: 0.5rem;">
        ● <span>Data Warehouse Online</span>
    </div>
    <div style="font-size: 0.8rem; color: #10b981; display: flex; align-items: center; gap: 0.5rem; margin-top: 0.2rem;">
        ● <span>Intelligence Engine Ready</span>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_global_sidebar() -> None:
    """Assembles and renders the complete global sidebar."""
    with st.sidebar:
        st.markdown(
            """
        <div style="margin-bottom: 2rem;">
            <div style="font-size: 0.75rem; font-weight: 600; letter-spacing: 0.25em; color: #6366f1; text-transform: uppercase;">Athena</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #f9fafb;">Decision Engine</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        render_workspace_navigation()
        render_context_selectors()

        st.markdown(
            "<div style='flex-grow: 1; height: 100px;'></div>", unsafe_allow_html=True
        )
        render_system_status()
