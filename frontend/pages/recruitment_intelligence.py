"""
frontend/pages/recruitment_intelligence.py — Recruitment Intelligence Workspace.
"""

import streamlit as st

from frontend.data.recruitment import search_candidates
from frontend.layout import render_page_header, render_section_header
from shared.schemas import RecruitmentCriteria


def render() -> None:
    render_page_header("Recruitment Intelligence", "Who should we sign?", "◎")

    col_filters, col_results = st.columns([1, 2])

    with col_filters:
        render_section_header("Search Criteria")
        with st.form("recruitment_form"):
            position = st.selectbox(
                "Position Group", ["Forward", "Midfielder", "Defender", "Goalkeeper"]
            )
            tactical_style = st.selectbox(
                "Tactical Fit",
                [
                    "None",
                    "Possession-Dominant",
                    "High Press",
                    "Direct and Progressive",
                    "Counter-Attacking",
                    "Defensive and Resilient",
                ],
            )

            st.markdown(
                "<div style='margin-top: 1rem; font-size: 0.85rem; color: #9ca3af;'>Required Capabilities (Weights)</div>",
                unsafe_allow_html=True,
            )
            w_bp = st.slider("Ball Progression", 0.0, 1.0, 0.0, 0.1)
            w_cc = st.slider("Chance Creation", 0.0, 1.0, 0.0, 0.1)
            w_at = st.slider("Attacking Threat", 0.0, 1.0, 1.0, 0.1)
            w_da = st.slider("Defensive Activity", 0.0, 1.0, 0.0, 0.1)

            st.form_submit_button(
                "Search Candidates", use_container_width=True
            )

    with col_results:
        render_section_header("Candidate Rankings")

        # Build Criteria
        required = {}
        if w_bp > 0:
            required["ball_progression"] = w_bp
        if w_cc > 0:
            required["chance_creation"] = w_cc
        if w_at > 0:
            required["attacking_threat"] = w_at
        if w_da > 0:
            required["defensive_activity"] = w_da

        criteria = RecruitmentCriteria(
            position=position,
            tactical_style=tactical_style if tactical_style != "None" else None,
            required_capabilities=required,
            max_results=5,
        )

        candidates = search_candidates(criteria)

        if not candidates:
            st.info("No candidates match the selected criteria.")
        else:
            for c in candidates:
                with st.expander(
                    f"#{c.rank} • {c.player.player_name} • Fit: {c.fit_score:.1f}"
                ):
                    # Expanded View
                    st.markdown(
                        f"**{c.player.team_name}** • {c.player.age_years} yrs • {c.player.minutes_played} mins"
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(
                            "<div style='color: #10b981; font-weight: 600; font-size: 0.85rem; margin-bottom: 0.5rem;'>STRENGTHS</div>",
                            unsafe_allow_html=True,
                        )
                        for s in c.strengths:
                            st.markdown(
                                f"<div style='font-size: 0.9rem; margin-bottom: 0.25rem;'>+ {s}</div>",
                                unsafe_allow_html=True,
                            )
                    with c2:
                        st.markdown(
                            "<div style='color: #ef4444; font-weight: 600; font-size: 0.85rem; margin-bottom: 0.5rem;'>TRADE-OFFS</div>",
                            unsafe_allow_html=True,
                        )
                        for t in c.trade_offs:
                            st.markdown(
                                f"<div style='font-size: 0.9rem; margin-bottom: 0.25rem;'>- {t}</div>",
                                unsafe_allow_html=True,
                            )

                    st.markdown(
                        "<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True
                    )

                    if c.explanation_context:
                        st.markdown(
                            "<div style='font-size: 0.8rem; color: #6b7280;'>EVIDENCE CONTEXT</div>",
                            unsafe_allow_html=True,
                        )
                        st.json(c.explanation_context)

                    st.button(
                        "Compare Player",
                        key=f"comp_{c.player.player_id}",
                        help="Add to comparison pool (Feature pending)",
                    )
