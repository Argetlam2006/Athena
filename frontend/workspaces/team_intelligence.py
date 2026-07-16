"""
frontend/pages/team_intelligence.py — Team Intelligence Workspace.
"""

import streamlit as st

from frontend.components.states import render_empty_state
from frontend.data.teams import get_team_profile
from frontend.layout import (
    render_divider,
    render_kpi_card,
    render_section_header,
)
from frontend.session import get_state


def render() -> None:
    st.markdown(
        """
    <div style="padding-top: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; color: #f9fafb;">
            <span style="color:#6366f1; margin-right:10px;">◉</span>Team Intelligence
        </h1>
    </div>
    """,
        unsafe_allow_html=True,
    )

    from frontend.components.selectors import render_team_selector
    render_team_selector(key_prefix="page")

    state = get_state()
    if not state.selected_team_id:
        render_empty_state(
            "◉",
            "No Team Selected",
            "Please search for a team above to view their intelligence profile.",
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
            "Avg Age", f"{team.avg_age:.1f}" if team.avg_age else "N/A"
        )
    with col3:
        render_kpi_card("Tactical Identity", team.style_label or "Balanced")
    with col4:
        # Placeholder KPI
        render_kpi_card("Capability Rating", "A-")
    render_divider()

    def render_team_decision_card(team_profile):
        from backend.intelligence.decision import DecisionEngine
        from frontend.data.players import get_all_players
        from frontend.data.teams import get_all_teams

        all_players = get_all_players()
        squad = [p for p in all_players if p.team_name == team_profile.team_name]
        cohort_teams = get_all_teams()

        card = DecisionEngine.build_team_decision_card(team_profile, squad, cohort_teams)

        def render_dependency(dep):
            top_players_html = "".join([f"<li><strong>{player}:</strong> {pct}% contribution</li>" for player, pct in list(dep.contributions.items())[:3]])
            return f"""
            <div style="margin-bottom: 0.8rem;">
                <strong style="color: #f9fafb;">{dep.capability_name}</strong>
                <ul style="margin: 0; padding-left: 1.2rem; color: #9ca3af; font-size: 0.85rem;">
                    {top_players_html}
                </ul>
            </div>
            """

        dependencies_html = "".join([render_dependency(d) for d in list(card.dependency_analysis.values())[:3]])

        gaps_html = "".join([
            f"<li><strong>{cap}:</strong> {gap} vs Elite Benchmark</li>"
            for cap, gap in sorted(card.gap_analysis.items(), key=lambda x: x[1])[:3]
        ])

        summary = f"""
        <div class="card-container" style="background: rgba(99, 102, 241, 0.05); border-color: rgba(99, 102, 241, 0.2);">
            <h3 style="margin-top: 0; color: #e5e7eb;">Team Decision Card</h3>
            <p style="color: #d1d5db; line-height: 1.6;">
                <strong>{team_profile.team_name}</strong> operates with a <strong>{card.tactical_identity}</strong> identity.
            </p>

            <div style="display: flex; gap: 2rem; margin-top: 1rem;">
                <div style="flex: 1;">
                    <h4 style="color: #10b981; margin-bottom: 0.5rem;">Key Dependencies</h4>
                    {dependencies_html}
                </div>
                <div style="flex: 1;">
                    <h4 style="color: #ef4444; margin-bottom: 0.5rem;">Critical Capability Gaps</h4>
                    <ul style="margin: 0; padding-left: 1.2rem; color: #9ca3af; font-size: 0.85rem;">
                        {gaps_html}
                    </ul>
                </div>
            </div>
        </div>
        """
        st.markdown(summary, unsafe_allow_html=True)

    render_team_decision_card(team)

    render_divider()
    col_style, col_depth = st.columns([2, 1])
    with col_style:
        render_section_header("Team Capability Radar")

        # Display team capability bars instead of radar chart
        cap_data = {
            "Ball Progression": team.avg_ball_progression,
            "Chance Creation": team.avg_chance_creation,
            "Ball Security": team.avg_ball_security,
            "Press Resistance": team.avg_press_resistance,
            "Defensive Activity": team.avg_defensive_activity,
            "Attacking Threat": team.avg_attacking_threat,
            "Physical Availability": team.avg_physical_availability,
            "Tactical Versatility": team.avg_tactical_versatility,
        }

        import pandas as pd
        cap_df = pd.DataFrame(list(cap_data.items()), columns=["Capability", "Score"])
        cap_df.set_index("Capability", inplace=True)
        st.bar_chart(cap_df, y="Score", height=350, color="#6366f1")

    with col_depth:
        render_section_header("Playing Style Notes")
        st.markdown(
            f"""
        <div class="card-container">
            <h4 style="margin-top: 0; color: #e5e7eb;">{team.style_label or "Balanced"}</h4>
            <p style="color: #9ca3af; font-size: 0.9rem; line-height: 1.5;">
                This team exhibits strong tendencies aligned with this tactical identity based on the aggregated capability profile of their core starters.
            </p>

            <h5 style="color: #10b981; margin-bottom: 0.2rem; margin-top: 1rem;">Primary Strengths</h5>
            <ul style="color: #d1d5db; font-size: 0.85rem; margin-top: 0;">
                {"".join(f"<li>{s}</li>" for s in team.strengths) if team.strengths else "<li>Balanced across capabilities</li>"}
            </ul>

            <h5 style="color: #ef4444; margin-bottom: 0.2rem; margin-top: 1rem;">Primary Weaknesses</h5>
            <ul style="color: #d1d5db; font-size: 0.85rem; margin-top: 0;">
                {"".join(f"<li>{w}</li>" for w in team.weaknesses) if team.weaknesses else "<li>No prominent weaknesses identified</li>"}
            </ul>
        </div>
        """,
            unsafe_allow_html=True,
        )

    render_divider()
    from frontend.components.ask_athena import render_ask_athena_section
    render_ask_athena_section()
