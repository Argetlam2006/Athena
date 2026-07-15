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


def render_context_selectors() -> None:
    """Renders global player and team selectors."""
    st.markdown("<div style='margin-top: 2rem; margin-bottom: 1rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>Global Context</div>", unsafe_allow_html=True)
    
    # In a real scenario, we would populate these from the database/warehouse
    # For the application shell, we use mock options
    players = {"Lionel Messi (PSG)": 1, "Kylian Mbappé (PSG)": 2, "Erling Haaland (MCI)": 3}
    teams = {"Paris Saint-Germain": 101, "Manchester City": 102}
    
    # Player Selection
    selected_player_name = st.selectbox(
        "Focus Player",
        options=["None"] + list(players.keys()),
        index=0,
        help="Select a player to focus all workspaces on."
    )
    if selected_player_name != "None":
        set_selected_player(players[selected_player_name])
    else:
        set_selected_player(None)
        
    # Team Selection
    selected_team_name = st.selectbox(
        "Focus Team",
        options=["None"] + list(teams.keys()),
        index=0,
        help="Select a team to focus all workspaces on."
    )
    if selected_team_name != "None":
        set_selected_team(teams[selected_team_name])
    else:
        set_selected_team(None)


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
