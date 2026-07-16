"""
frontend/pages/dashboard.py — Executive Dashboard Workspace.
"""

import streamlit as st

from frontend.components.ask_athena import render_hero_prompt
from frontend.data.dashboard import get_dashboard_summary
from frontend.layout import (
    render_divider,
    render_kpi_card,
    render_section_header,
)


def render() -> None:
    st.markdown(
        """
    <div style="padding-top: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; color: #f9fafb;">
            <span style="color:#6366f1; margin-right:10px;">⬡</span>Executive Dashboard
        </h1>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # Primary Interaction
    render_hero_prompt()

    summary = get_dashboard_summary()

    render_section_header("Platform Overview")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Players Indexed", summary["unique_players"])
    with col2:
        render_kpi_card("Total Teams", summary["total_teams"])
    with col3:
        render_kpi_card("Leagues Indexed", summary["total_leagues"])
    with col4:
        render_kpi_card("System Health", summary["database_health"])

    render_divider()

    # Dataset Transparency
    render_section_header("Dataset Transparency")
    st.markdown(
        f"""
        <div style="background: #111827; padding: 1.5rem; border-radius: 8px; border: 1px solid #374151;">
            <p style="color: #e5e7eb; line-height: 1.6; margin-top: 0;">
                Athena is built on the philosophy of <strong>Evidence Before AI</strong>.
                Rather than relying on Large Language Models to hallucinate football knowledge,
                Athena grounds all intelligence entirely in a deterministic dataset.
            </p>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap: 1rem; margin-top: 1.5rem; text-align: center;">
                <div>
                    <div style="color: #6366f1; font-size: 1.5rem; font-weight: 700;">{summary['unique_players']:,}</div>
                    <div style="color: #9ca3af; font-size: 0.85rem; text-transform: uppercase;">Players Indexed</div>
                </div>
                <div>
                    <div style="color: #6366f1; font-size: 1.5rem; font-weight: 700;">{summary['career_profiles']:,}</div>
                    <div style="color: #9ca3af; font-size: 0.85rem; text-transform: uppercase;">Career Analyses</div>
                </div>
                <div>
                    <div style="color: #6366f1; font-size: 1.5rem; font-weight: 700;">{summary['season_profiles']:,}</div>
                    <div style="color: #9ca3af; font-size: 0.85rem; text-transform: uppercase;">Season Analyses</div>
                </div>
                <div>
                    <div style="color: #6366f1; font-size: 1.5rem; font-weight: 700;">{summary['competition_profiles']:,}</div>
                    <div style="color: #9ca3af; font-size: 0.85rem; text-transform: uppercase;">Competition Analyses</div>
                </div>
                <div>
                    <div style="color: #6366f1; font-size: 1.5rem; font-weight: 700;">{summary['total_teams']:,}</div>
                    <div style="color: #9ca3af; font-size: 0.85rem; text-transform: uppercase;">Indexed Teams</div>
                </div>
            </div>
            <p style="color: #9ca3af; font-size: 0.85rem; margin-bottom: 0; margin-top: 1.5rem; border-top: 1px solid #1f2937; padding-top: 1rem;">
                <em>Note: Player intelligence is strictly limited to the seasons and competitions available in the loaded warehouse.</em>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

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
