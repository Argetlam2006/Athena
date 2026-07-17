"""
frontend/pages/team_intelligence.py — Team Intelligence Workspace.
"""

import streamlit as st

from frontend.components.states import render_empty_state
from frontend.data.team_service import get_collective_profile
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

    team = get_collective_profile(state.selected_team_id)
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

    squad_size = team.squad_size
    avg_age = team.avg_age

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Squad Size", squad_size)
    with col2:
        render_kpi_card("Avg Age", f"{avg_age:.1f}" if avg_age else "N/A")
    with col3:
        identity_label = team.identity.primary_identity if team.identity else "Balanced"
        render_kpi_card("Tactical Identity", identity_label)
    with col4:
        from backend.collective.engine import compute_team_grade

        grade = compute_team_grade(team)
        render_kpi_card("Capability Rating", grade)
    render_divider()

    def render_team_decision_card(team_profile):
        from frontend.data.team_service import get_team_decision_card

        card = get_team_decision_card(team_profile)

        def render_dependency(dep):
            top_players_html = "".join(
                [
                    f"<li><strong>{player}:</strong> {pct}% contribution</li>"
                    for player, pct in list(dep.contributions.items())[:3]
                ]
            )
            return f"""<div style="margin-bottom: 0.8rem;">
<strong style="color: #f9fafb;">{dep.capability_name}</strong>
<ul style="margin: 0; padding-left: 1.2rem; color: #9ca3af; font-size: 0.85rem;">
{top_players_html}
</ul>
</div>"""

        dependencies_html = "".join(
            [render_dependency(d) for d in list(card.dependency_analysis.values())[:3]]
        )

        gaps_html = "".join(
            [
                f"<li><strong>{cap}:</strong> {gap} vs Elite Benchmark</li>"
                for cap, gap in sorted(card.gap_analysis.items(), key=lambda x: x[1])[
                    :3
                ]
            ]
        )

        summary = f"""<div class="card-container" style="background: rgba(99, 102, 241, 0.05); border-color: rgba(99, 102, 241, 0.2);">
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
</div>"""
        st.markdown(summary, unsafe_allow_html=True)

    render_team_decision_card(team)

    render_divider()
    col_style, col_depth = st.columns([2, 1])
    with col_style:
        render_section_header("Team Capability Radar")

        # Display team capability bars instead of radar chart
        cap_data = team.as_radar_dict()

        import altair as alt
        import pandas as pd

        cap_df = pd.DataFrame(list(cap_data.items()), columns=["Capability", "Score"])

        bars = (
            alt.Chart(cap_df)
            .mark_bar(color="#6366f1", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X(
                    "Capability:N",
                    sort=None,
                    axis=alt.Axis(
                        labelAngle=-45,
                        labelColor="#9ca3af",
                        title=None,
                        labelFontSize=12,
                    ),
                ),
                y=alt.Y(
                    "Score:Q",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(
                        grid=True,
                        gridColor="rgba(255,255,255,0.1)",
                        labelColor="#9ca3af",
                        title=None,
                    ),
                ),
            )
        )
        text = bars.mark_text(
            align="center",
            baseline="bottom",
            dy=-5,
            color="#f9fafb",
            fontSize=13,
            fontWeight=600,
        ).encode(text=alt.Text("Score:Q", format=".1f"))
        chart = (
            (bars + text)
            .properties(height=350)
            .configure_view(strokeWidth=0)
            .configure_axis(domain=False, ticks=False)
        )
        st.altair_chart(chart, use_container_width=True)

    with col_depth:
        render_section_header("Playing Style Notes")
        identity_label = team.identity.primary_identity if team.identity else "Balanced"

        # Derive strengths/weaknesses from avg_capabilities
        strengths = [
            cap.replace("_", " ").title()
            for cap, val in team.avg_capabilities.items()
            if val >= 80.0
        ]
        weaknesses = [
            cap.replace("_", " ").title()
            for cap, val in team.avg_capabilities.items()
            if val <= 60.0
        ]

        st.markdown(
            f"""<div class="card-container">
<h4 style="margin-top: 0; color: #e5e7eb;">{identity_label}</h4>
<p style="color: #9ca3af; font-size: 0.9rem; line-height: 1.5;">
This team exhibits strong tendencies aligned with this tactical identity based on the aggregated capability profile of their core starters.
</p>
<h5 style="color: #10b981; margin-bottom: 0.2rem; margin-top: 1rem;">Primary Strengths</h5>
<ul style="color: #d1d5db; font-size: 0.85rem; margin-top: 0;">
{"".join(f"<li>{s}</li>" for s in strengths) if strengths else "<li>Balanced across capabilities</li>"}
</ul>
<h5 style="color: #ef4444; margin-bottom: 0.2rem; margin-top: 1rem;">Primary Weaknesses</h5>
<ul style="color: #d1d5db; font-size: 0.85rem; margin-top: 0;">
{"".join(f"<li>{w}</li>" for w in weaknesses) if weaknesses else "<li>No prominent weaknesses identified</li>"}
</ul>
</div>""",
            unsafe_allow_html=True,
        )

    render_divider()
    from frontend.components.ask_athena import render_ask_athena_section

    render_ask_athena_section()
