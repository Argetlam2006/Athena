"""
frontend/pages/team_intelligence.py — Team Intelligence Workspace.
"""

import streamlit as st

from frontend.components.states import render_empty_state
from frontend.data.teams import get_team_profile
from frontend.layout import (
    render_divider,
    render_kpi_card,
    render_page_header,
    render_section_header,
)
from frontend.session import get_state


def render() -> None:
    render_page_header("Team Intelligence", "How does this team play?", "◉")

    state = get_state()
    if not state.selected_team_id:
        render_empty_state(
            "◉",
            "No Team Selected",
            "Please select a focus team from the global context menu in the sidebar to view their intelligence profile.",
        )
        return

    team = get_team_profile(state.selected_team_id)
    if not team:
        render_empty_state(
            "⚠",
            "Team Not Found",
            "The selected team could not be found in the database.",
        )
        return

    st.markdown(
        f"""
    <h2 style="margin: 0; color: #f9fafb;">{team.team_name}</h2>
    <div style="color: #9ca3af; font-size: 1.1rem; margin-bottom: 1rem;">
        {team.competition} • {team.season}
    </div>
    """,
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Squad Size", team.squad_size)
    with col2:
        render_kpi_card(
            "Avg Age", f"{team.average_age:.1f}" if team.average_age else "N/A"
        )
    with col3:
        render_kpi_card("Tactical Identity", team.style_label or "Balanced")
    with col4:
        # Placeholder KPI
        render_kpi_card("Capability Rating", "A-")

    render_divider()

    col_style, col_depth = st.columns([2, 1])
    with col_style:
        render_section_header("Team Capability Radar")
        st.info(
            "Team-aggregated capability radar will be rendered here. (Awaiting squad aggregation layer)"
        )

    with col_depth:
        render_section_header("Playing Style Notes")
        st.markdown(
            f"""
        <div class="card-container">
            <h4 style="margin-top: 0; color: #e5e7eb;">{team.style_label or "Balanced"}</h4>
            <p style="color: #9ca3af; font-size: 0.9rem; line-height: 1.5;">
                This team exhibits strong tendencies aligned with this tactical identity based on the aggregated capability profile of their core starters.
            </p>
        </div>
        """,
            unsafe_allow_html=True,
        )
