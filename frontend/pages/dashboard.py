"""
frontend/pages/dashboard.py — Executive Dashboard Workspace.
"""

import streamlit as st

from frontend.data.dashboard import get_dashboard_summary
from frontend.layout import (
    render_divider,
    render_kpi_card,
    render_page_header,
    render_section_header,
)


def render() -> None:
    render_page_header(
        title="Executive Dashboard",
        subtitle="What deserves my attention today?",
        icon="⬡",
    )

    summary = get_dashboard_summary()

    render_section_header("Platform Overview")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Total Players", summary["total_players"])
    with col2:
        render_kpi_card("Total Teams", summary["total_teams"])
    with col3:
        render_kpi_card("Leagues Indexed", summary["total_leagues"])
    with col4:
        render_kpi_card("System Health", summary["database_health"])

    render_divider()

    col_feat1, col_feat2 = st.columns(2)

    with col_feat1:
        render_section_header("Featured Player")
        p = summary["featured_player"]
        if p:
            st.markdown(
                f"""
            <div class="card-container">
                <h3 style="margin-top: 0; color: #f9fafb;">{p.player_name}</h3>
                <p style="color: #9ca3af; font-size: 0.9rem;">{p.position_group} • {p.team_name}</p>
                <div style="margin-top: 1rem; color: #818cf8; font-size: 0.85rem; font-weight: 600;">{p.archetype}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info("No featured player currently available.")

    with col_feat2:
        render_section_header("Featured Team")
        t = summary["featured_team"]
        if t:
            st.markdown(
                f"""
            <div class="card-container">
                <h3 style="margin-top: 0; color: #f9fafb;">{t.team_name}</h3>
                <p style="color: #9ca3af; font-size: 0.9rem;">{t.competition} • Squad: {t.squad_size}</p>
                <div style="margin-top: 1rem; color: #818cf8; font-size: 0.85rem; font-weight: 600;">{t.style_label}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.info("No featured team currently available.")
