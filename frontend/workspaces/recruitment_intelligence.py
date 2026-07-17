"""
frontend/pages/recruitment_intelligence.py — Recruitment Intelligence Workspace.
"""

import streamlit as st

from backend.intelligence.roles import ROLE_FAMILIES
from frontend.data.recruitment_service import search_candidates
from frontend.layout import render_section_header
from shared.schemas import RecruitmentCriteria

# Map broad position to available styles (archetypes)
STYLE_MAP = {
    "Forward": [
        "Elite Goal Scorer",
        "Target Man",
        "Complete Forward",
        "Direct Winger",
        "Creative Forward",
        "Creative Playmaker",
        "Creative Winger",
    ],
    "Midfielder": [
        "Deep-Lying Playmaker",
        "Box-to-Box Engine",
        "Press-Resistant Anchor",
        "Midfield Destroyer",
        "Creative Playmaker",
    ],
    "Defender": [
        "Ball-Playing Defender",
        "Progressive Fullback",
        "Traditional Defender",
        "Defensive Fullback",
    ],
    "Goalkeeper": ["Goalkeeper"],
}

TRAIT_MAP = {
    "Goalscoring": "attacking_threat",
    "Chance Creation": "chance_creation",
    "Progressive Passing": "ball_progression",
    "Ball Carrying": "ball_progression",
    "Press Resistance": "press_resistance",
    "Defensive Work": "defensive_activity",
    "Ball Retention": "ball_security",
    "Aerial Ability": "defensive_activity",
}


def get_role_importance(style_name: str) -> dict[str, float]:
    for family, data in ROLE_FAMILIES.items():
        if style_name in data["archetypes"] or style_name == family:
            return data["importance_vector"].copy()
    return ROLE_FAMILIES["Balanced"]["importance_vector"].copy()


def render() -> None:
    st.markdown(
        """
    <div style="padding-top: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; color: #f9fafb;">
            <span style="color:#6366f1; margin-right:10px;">◎</span>Recruitment Intelligence
        </h1>
    </div>
    """,
        unsafe_allow_html=True,
    )

    if "parsed_query" not in st.session_state:
        st.session_state.parsed_query = None

    query = st.text_input(
        "Describe the player",
        placeholder="e.g. 'Need a pressing striker who can contribute to build-up play.'",
    )

    if st.button("Analyse Query", key="analyse_btn"):
        if query:
            with st.spinner("Analyzing request..."):
                from backend.explanation.parsers import parse_natural_language_scouting

                st.session_state.parsed_query = parse_natural_language_scouting(query)
        else:
            st.session_state.parsed_query = None

    if st.session_state.parsed_query:
        if st.session_state.parsed_query.get("error"):
            st.error(
                f"Natural Language Parsing Failed: {st.session_state.parsed_query['error']}"
            )
        else:
            pq = st.session_state.parsed_query
        st.markdown(
            """
            <div style="background: #1f2937; padding: 1.5rem; border-radius: 8px; border: 1px solid #374151; margin-bottom: 1.5rem;">
                <h3 style="margin-top: 0; color: #f9fafb; font-size: 1.2rem;">Athena understood</h3>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(
                f"**Position**<br/>✓ {pq.get('position', 'Any')}",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"**Style**<br/>✓ {pq.get('playing_style', 'Balanced')}",
                unsafe_allow_html=True,
            )
        with c3:
            traits_str = (
                "<br/>".join([f"✓ {t}" for t in pq.get("traits", [])])
                if pq.get("traits")
                else "None specified"
            )
            st.markdown(f"**Desired Traits**<br/>{traits_str}", unsafe_allow_html=True)

        st.markdown(
            f"<div style='margin-top: 1rem; font-size: 0.85rem; color: #9ca3af;'><strong>Interpretation Confidence:</strong> {pq.get('confidence', 'Medium')}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
    col_filters, col_results = st.columns([1, 2])

    with col_filters:
        render_section_header("Structured Search")

        # Determine defaults based on parsed query
        default_pos_idx = 1  # Midfielder
        if st.session_state.parsed_query and st.session_state.parsed_query.get(
            "position"
        ):
            pos = st.session_state.parsed_query["position"]
            opts = ["Forward", "Midfielder", "Defender", "Goalkeeper"]
            if pos in opts:
                default_pos_idx = opts.index(pos)

        with st.form("recruitment_form"):
            position = st.selectbox(
                "Choose Position",
                ["Forward", "Midfielder", "Defender", "Goalkeeper"],
                index=default_pos_idx,
            )

            style_options = STYLE_MAP.get(position, ["Balanced"])
            default_style_idx = 0
            if st.session_state.parsed_query and st.session_state.parsed_query.get(
                "playing_style"
            ):
                style = st.session_state.parsed_query["playing_style"]
                if style in style_options:
                    default_style_idx = style_options.index(style)

            playing_style = st.selectbox(
                "Choose Playing Style", style_options, index=default_style_idx
            )

            st.markdown(
                "<div style='margin-top: 1rem; font-size: 0.9rem; font-weight: 600;'>Must Have Traits</div>",
                unsafe_allow_html=True,
            )

            parsed_traits = []
            if st.session_state.parsed_query and st.session_state.parsed_query.get(
                "traits"
            ):
                parsed_traits = st.session_state.parsed_query["traits"]

            traits_selected = []
            for trait in TRAIT_MAP.keys():
                is_checked = trait in parsed_traits
                if st.checkbox(trait, value=is_checked):
                    traits_selected.append(trait)

            with st.expander("▼ Advanced Search"):
                st.markdown(
                    "<div style='font-size: 0.85rem; color: #9ca3af;'>Raw Capability Weights</div>",
                    unsafe_allow_html=True,
                )
                w_bp = st.slider("Ball Progression", 0.0, 1.0, 0.0, 0.1)
                w_cc = st.slider("Chance Creation", 0.0, 1.0, 0.0, 0.1)
                w_at = st.slider("Attacking Threat", 0.0, 1.0, 0.0, 0.1)
                w_da = st.slider("Defensive Activity", 0.0, 1.0, 0.0, 0.1)
                w_bs = st.slider("Ball Security", 0.0, 1.0, 0.0, 0.1)
                w_pr = st.slider("Press Resistance", 0.0, 1.0, 0.0, 0.1)

            submitted = st.form_submit_button(
                "Search Candidates", use_container_width=True
            )

    with col_results:
        render_section_header("Candidate Rankings")

        if submitted:
            required = get_role_importance(playing_style)

            for trait in traits_selected:
                cap = TRAIT_MAP[trait]
                if cap in required:
                    required[cap] += 2.0
                else:
                    required[cap] = 2.0

            if w_bp > 0:
                required["ball_progression"] = w_bp
            if w_cc > 0:
                required["chance_creation"] = w_cc
            if w_at > 0:
                required["attacking_threat"] = w_at
            if w_da > 0:
                required["defensive_activity"] = w_da
            if w_bs > 0:
                required["ball_security"] = w_bs
            if w_pr > 0:
                required["press_resistance"] = w_pr

            criteria = RecruitmentCriteria(
                position=position,
                tactical_style=None,
                required_capabilities=required,
                max_results=5,
            )

            candidates = search_candidates(criteria)

            if not candidates:
                st.info("No candidates match the selected criteria.")
            else:
                for c in candidates:
                    role_fam = "Balanced"
                    if c.player.display_archetype:
                        for fam, data in ROLE_FAMILIES.items():
                            if c.player.display_archetype in data["archetypes"]:
                                role_fam = fam
                                break

                    stars = (
                        "★★★★★ Excellent Fit"
                        if c.fit_score > 85
                        else "★★★★☆ Strong Fit"
                        if c.fit_score > 70
                        else "★★★☆☆ Good Fit"
                    )

                    with st.expander(f"#{c.rank} • {c.player.player_name} • {stars}"):
                        st.markdown(f"**Role Family:** {role_fam}")

                        st.markdown("##### Why Athena recommends him")
                        has_strengths = False
                        if c.player.capability_profile:
                            for (
                                cap_name,
                                cap_obj,
                            ) in c.player.capability_profile.__dict__.items():
                                if cap_obj and getattr(cap_obj, "score", 0) > 85:
                                    st.markdown(
                                        f"✓ Elite {cap_name.replace('_', ' ').title()}"
                                    )
                                    has_strengths = True
                                elif cap_obj and getattr(cap_obj, "score", 0) > 75:
                                    st.markdown(
                                        f"✓ Strong {cap_name.replace('_', ' ').title()}"
                                    )
                                    has_strengths = True
                        if not has_strengths:
                            st.markdown("✓ Balanced general profile")

                        if c.trade_offs_negative:
                            st.markdown("##### Trade-offs")
                            for t in c.trade_offs_negative:
                                st.markdown(f"• {t}")

                        st.markdown(f"**Confidence:** {c.confidence.title()}")

    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
    from frontend.components.ask_athena import render_ask_athena_section

    render_ask_athena_section()
