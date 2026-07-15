"""
frontend/sidebar.py — Global persistent sidebar.

Renders navigation, context selectors, system status, and the Ask Athena placeholder.
Directly reads from and writes to the centralized session state.
"""

import streamlit as st
from shared.config.navigation import WORKSPACES
from frontend.session import get_state, set_active_workspace, set_selected_player, set_selected_team


def render_workspace_navigation() -> None:
    """Renders dynamic workspace links based on config."""
    state = get_state()
    
    st.markdown("<div style='margin-bottom: 1rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>Intelligence Workspaces</div>", unsafe_allow_html=True)
    
    for workspace in WORKSPACES:
        if workspace.status == "live":
            # Determine if this is the active workspace
            is_active = state.active_workspace_id == workspace.id
            
            # Simple button rendering to switch workspaces
            # We use a trick: if active, display it differently
            # For Streamlit, st.button is the primary way to handle sidebar clicks
            
            # Button key must be unique
            btn_key = f"nav_{workspace.id}"
            
            if is_active:
                st.markdown(f"**{workspace.icon} {workspace.name}**")
            else:
                if st.button(f"{workspace.icon} {workspace.name}", key=btn_key, use_container_width=True):
                    set_active_workspace(workspace.id)
                    st.rerun()


from frontend.data.players import get_all_players
from frontend.data.teams import get_all_teams

def render_context_selectors() -> None:
    """Renders global player and team selectors."""
    st.markdown("<div style='margin-top: 2rem; margin-bottom: 1rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>Global Context</div>", unsafe_allow_html=True)
    
    # Fetch from data layer
    players = get_all_players()
    teams = get_all_teams()
    
    player_options = {"None": None}
    for p in players:
        player_options[f"{p.player_name} ({p.team_name})"] = p.player_id
        
    team_options = {"None": None}
    for t in teams:
        team_options[t.team_name] = t.team_id
    
    # Player Selection
    selected_player_name = st.selectbox(
        "Focus Player",
        options=list(player_options.keys()),
        index=0,
        help="Select a player to focus all workspaces on."
    )
    set_selected_player(player_options[selected_player_name])
        
    # Team Selection
    selected_team_name = st.selectbox(
        "Focus Team",
        options=list(team_options.keys()),
        index=0,
        help="Select a team to focus all workspaces on."
    )
    set_selected_team(team_options[selected_team_name])


def render_system_status() -> None:
    """Renders the system status indicator."""
    st.markdown("<div style='margin-top: 2rem; margin-bottom: 0.5rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>System Status</div>", unsafe_allow_html=True)
    
    # Mocking status check
    st.markdown("""
    <div style="font-size: 0.8rem; color: #10b981; display: flex; align-items: center; gap: 0.5rem;">
        ● <span>Data Warehouse Online</span>
    </div>
    <div style="font-size: 0.8rem; color: #10b981; display: flex; align-items: center; gap: 0.5rem; margin-top: 0.2rem;">
        ● <span>Intelligence Engine Ready</span>
    </div>
    """, unsafe_allow_html=True)


def render_global_sidebar() -> None:
    """Assembles and renders the complete global sidebar."""
    with st.sidebar:
        st.markdown("""
        <div style="margin-bottom: 2rem;">
            <div style="font-size: 0.75rem; font-weight: 600; letter-spacing: 0.25em; color: #6366f1; text-transform: uppercase;">Athena</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #f9fafb;">Decision Engine</div>
        </div>
        """, unsafe_allow_html=True)
        
        render_workspace_navigation()
        render_context_selectors()
        
        st.markdown("<div style='flex-grow: 1; height: 100px;'></div>", unsafe_allow_html=True)
        render_system_status()
