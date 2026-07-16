"""
frontend/pages/player_intelligence.py — Player Intelligence Workspace.
"""

import streamlit as st

from frontend.components.states import render_empty_state
from frontend.layout import render_divider, render_section_header
from frontend.session import get_state


def render_decision_card(player) -> None:
    """Generates a deterministic decision card using the Decision Intelligence layer."""
    if not player.capability_profile:
        return

    from backend.intelligence.decision import DecisionEngine
    from frontend.data.players import get_players_by_position

    # Use positional peers as the dynamic cohort
    cohort = get_players_by_position(player.position_group)
    card = DecisionEngine.build_player_decision_card(player, cohort)

    def render_cap_explanation(exp):
        drivers_html = "".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in exp.drivers.items()])
        return f"""
        <div style="margin-bottom: 0.5rem;">
            <strong style="color: #f9fafb;">{exp.capability_name} ({exp.score})</strong>
            <ul style="margin: 0; padding-left: 1.2rem; color: #9ca3af; font-size: 0.85rem;">
                {drivers_html}
            </ul>
        </div>
        """

    elite_html = "".join([render_cap_explanation(e) for e in card.elite_traits]) if card.elite_traits else "<p style='color: #9ca3af; font-size: 0.9rem;'>No elite outliers identified against positional peers.</p>"
    weak_html = "".join([render_cap_explanation(w) for w in card.weak_areas]) if card.weak_areas else "<p style='color: #9ca3af; font-size: 0.9rem;'>No significant weaknesses against positional peers.</p>"

    summary = f"""
    <div class="card-container" style="background: rgba(99, 102, 241, 0.05); border-color: rgba(99, 102, 241, 0.2);">
        <h3 style="margin-top: 0; color: #e5e7eb;">Player Decision Card</h3>
        <p style="color: #d1d5db; line-height: 1.6;">
            <strong>{player.player_name}</strong> operates as a <strong>{card.primary_role}</strong>.
        </p>

        <div style="display: flex; gap: 2rem; margin-top: 1rem;">
            <div style="flex: 1;">
                <h4 style="color: #10b981; margin-bottom: 0.5rem;">Elite Traits</h4>
                {elite_html}
            </div>
            <div style="flex: 1;">
                <h4 style="color: #ef4444; margin-bottom: 0.5rem;">Weak Areas</h4>
                {weak_html}
            </div>
        </div>
    </div>
    """
    st.markdown(summary, unsafe_allow_html=True)



def render() -> None:
    st.markdown(
        """
    <div style="padding-top: 1rem; margin-bottom: 1rem;">
        <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; color: #f9fafb;">
            <span style="color:#6366f1; margin-right:10px;">◈</span>Player Intelligence
        </h1>
    </div>
    """,
        unsafe_allow_html=True,
    )

    from frontend.components.selectors import render_player_selector
    render_player_selector(key_prefix="page")

    state = get_state()
    if not state.selected_player_id:
        render_empty_state(
            "◈",
            "No Player Selected",
            "Please search for a player above to view their intelligence profile.",
        )
        return

    from frontend.data.players import get_player_career
    career = get_player_career(state.selected_player_id)

    if not career:
        render_empty_state(
            "⚠",
            "Player Not Found",
            "The selected player could not be found in the database.",
        )
        return

    # Find career profile index
    from shared.schemas import ProfileType
    career_idx = next((i for i, p in enumerate(career) if getattr(p, "profile_type", None) == ProfileType.CAREER or p.season == "Career"), -1)

    segment_key = f"segment_idx_{state.selected_player_id}"
    if segment_key not in st.session_state:
        st.session_state[segment_key] = career_idx if career_idx != -1 else 0

    # Ensure index is within bounds
    if st.session_state[segment_key] >= len(career):
        st.session_state[segment_key] = career_idx if career_idx != -1 else 0

    # Group remaining career by season for later
    from collections import defaultdict
    seasons_dict = defaultdict(list)
    for i, profile in enumerate(career):
        if i == career_idx:
            continue
        seasons_dict[profile.season].append((i, profile))

    player = career[st.session_state[segment_key]]

    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

    # Main Profile Header
    col1, col2 = st.columns([2, 1])
    with col1:
        # Construct header metadata without placeholders
        metadata_parts = []
        if getattr(player, "profile_type", None) == ProfileType.CAREER or player.season == "Career":
            # Add dynamic career metadata
            season_count = len(seasons_dict)
            latest_season = max(seasons_dict.keys()) if season_count > 0 else "Unknown"
            metadata_parts.append("Career Overview")
            metadata_parts.append(f"{season_count} Indexed Seasons")
            metadata_parts.append(f"Latest: {latest_season}")
        else:
            if player.position_group and player.position_group != "Unknown":
                metadata_parts.append(player.position_group)
            if player.team_name and player.team_name != "Unknown":
                metadata_parts.append(player.team_name)
            if player.age_years is not None:
                metadata_parts.append(f"{player.age_years} yrs")

        metadata_str = " • ".join(metadata_parts)

        st.markdown(
            f"""
        <h2 style="margin: 0; color: #f9fafb;">{player.player_name}</h2>
        <div style="color: #9ca3af; font-size: 1.1rem; margin-bottom: 1rem;">
            {metadata_str}
            <span style="font-size: 0.8rem; background: #374151; padding: 0.1rem 0.5rem; border-radius: 4px; margin-left: 0.5rem;">Dataset Context: Latest available season {player.season}</span>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col2:
        if player.archetype:
            st.markdown(
                f"""
            <div style="text-align: right;">
                <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: #4b5563;">Role Classification</div>
                <div style="font-size: 1.2rem; font-weight: 600; color: #818cf8;">{player.archetype}</div>
                <div style="font-size: 0.85rem; color: #6b7280;">{player.archetype_description}</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

    render_divider()

    # Explainable Overall Rating
    cap = player.capability_profile
    if cap and getattr(cap, "overall_rating", None):
        st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
        # Determine rating label
        r = cap.overall_rating
        if r >= 85:
            rating_label = "Elite"
            rating_color = "#10b981"
        elif r >= 75:
            rating_label = "Excellent"
            rating_color = "#3b82f6"
        elif r >= 60:
            rating_label = "Good"
            rating_color = "#f59e0b"
        else:
            rating_label = "Average"
            rating_color = "#6b7280"

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            st.markdown(
                f"""
                <div style="text-align: center; background: #1f2937; padding: 1.5rem; border-radius: 8px; border: 1px solid #374151;">
                    <div style="color: #9ca3af; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem;">Overall Rating</div>
                    <div style="color: {rating_color}; font-size: 3rem; font-weight: 700; line-height: 1;">{r:.1f}</div>
                    <div style="color: #d1d5db; font-size: 1.1rem; margin-top: 0.5rem; font-weight: 500;">{rating_label}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        scores = cap.as_radar_dict()
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_scores = sorted_scores[:3]
        bottom_scores = sorted_scores[-3:]

        with c2:
            st.markdown(
                """
                <div style="background: #1f2937; padding: 1rem; border-radius: 8px; border: 1px solid #374151; height: 100%;">
                    <div style="color: #9ca3af; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;">Primary Contributors</div>
                """,
                unsafe_allow_html=True
            )
            for k, _v in top_scores:
                st.markdown(f"<div style='color: #10b981; font-weight: 500; margin-bottom: 0.25rem;'>+ {k}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with c3:
            st.markdown(
                """
                <div style="background: #1f2937; padding: 1rem; border-radius: 8px; border: 1px solid #374151; height: 100%;">
                    <div style="color: #9ca3af; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;">Lower Contributors</div>
                """,
                unsafe_allow_html=True
            )
            for k, _v in bottom_scores:
                st.markdown(f"<div style='color: #ef4444; font-weight: 500; margin-bottom: 0.25rem;'>− {k}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        render_divider()

    # Player Snapshot
    fv = player.feature_vector
    if fv:
        raw_metrics = {
            "Matches": fv.matches_played,
            "Minutes": int(fv.minutes_played) if fv.minutes_played is not None else None,
            "Goals p90": f"{fv.goals_p90:.2f}" if fv.goals_p90 is not None else None,
            "Assists p90": f"{fv.goal_assists_p90:.2f}" if fv.goal_assists_p90 is not None else None,
            "xG p90": f"{fv.npxg_p90:.2f}" if fv.npxg_p90 is not None else None,
            "Prog Passes": f"{fv.progressive_passes_p90:.1f}" if fv.progressive_passes_p90 is not None else None,
            "Prog Carries": f"{fv.progressive_carries_p90:.1f}" if fv.progressive_carries_p90 is not None else None
        }

        # Omit any None/N/A values
        metrics = {k: v for k, v in raw_metrics.items() if v is not None}

        cols = st.columns(len(metrics))
        for i, (label, val) in enumerate(metrics.items()):
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="background: #1f2937; padding: 1rem; border-radius: 8px; border: 1px solid #374151; text-align: center;">
                        <div style="color: #9ca3af; font-size: 0.8rem; margin-bottom: 0.25rem;">{label}</div>
                        <div style="color: #f9fafb; font-size: 1.25rem; font-weight: 600;">{val}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    render_divider()

    # Render Strengths/Weaknesses if Career Overview
    if player.season == "Career" and cap:
        st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
        render_section_header("Career Analysis")

        c1, c2 = st.columns(2)
        strengths = []
        weaknesses = []
        for metric, score in cap.as_radar_dict().items():
            if score >= 80:
                strengths.append(f"Elite {metric}")
            elif score >= 70:
                strengths.append(f"Excellent {metric}")
            elif score <= 40:
                weaknesses.append(f"Limited {metric}")

        with c1:
            st.markdown("#### Strengths")
            if strengths:
                for s in strengths:
                    st.markdown(f"- ✅ <span style='color: #10b981;'>{s}</span>", unsafe_allow_html=True)
            else:
                st.caption("No significant deterministic strengths identified.")

        with c2:
            st.markdown("#### Weaknesses")
            if weaknesses:
                for w in weaknesses:
                    st.markdown(f"- ⚠️ <span style='color: #ef4444;'>{w}</span>", unsafe_allow_html=True)
            else:
                st.caption("No significant deterministic weaknesses identified.")

        render_divider()

    # Scout Summary
    render_decision_card(player)

    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

    col_cap, col_sig = st.columns([2, 1])
    with col_cap:
        render_section_header("Capability Profile")
        if player.capability_profile:
            # We would render a real radar chart here with Plotly or Altair.
            # For the structural phase, we render the raw bars.
            cap = player.capability_profile
            for metric in [
                "ball_progression",
                "chance_creation",
                "ball_security",
                "press_resistance",
                "defensive_activity",
                "attacking_threat",
                "physical_availability",
                "tactical_versatility",
            ]:
                val_obj = getattr(cap, metric)
                if val_obj:
                    score = val_obj.score
                    name = metric.replace("_", " ").title()
                    # A simple CSS bar
                    st.markdown(
                        f"""
                    <div style="margin-bottom: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                            <span style="color: #d1d5db;">{name}</span>
                            <span style="color: #9ca3af; font-weight: 600;">{score:.1f}</span>
                        </div>
                        <div style="width: 100%; background-color: #1f2937; border-radius: 4px; height: 8px;">
                            <div style="width: {score}%; background-color: {"#10b981" if score >= 75 else "#3b82f6" if score >= 50 else "#ef4444"}; height: 100%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
        else:
            st.info("Capability profile not generated.")

    with col_sig:
        render_section_header("Decision Signals")
        if player.decision_signals:
            for sig in player.decision_signals:
                st.markdown(
                    f"""
                <div style="background: #111827; border-left: 3px solid #6366f1; padding: 0.75rem 1rem; margin-bottom: 0.5rem; font-size: 0.9rem; color: #e5e7eb;">
                    {sig.replace("_", " ").title()}
                </div>
                """,
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div style='color: #6b7280; font-size: 0.9rem;'>No active signals.</div>",
                unsafe_allow_html=True,
            )

    render_divider()

    # Chat
    render_section_header("Ask Athena")
    from frontend.components.ask_athena import render_ask_athena_section

    render_ask_athena_section()

    render_divider()

    # Career Segments Timeline
    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
    render_section_header("Career Timeline")
    st.markdown("<p style='color: #9ca3af; font-size: 0.9rem;'>Select a specific club and season context to drill down into the profile.</p>", unsafe_allow_html=True)

    # Render Career Overview Button
    if career_idx != -1:
        is_career_selected = (st.session_state[segment_key] == career_idx)
        btn_label = "✅ Career Overview" if is_career_selected else "Career Overview"
        if st.button(btn_label, key=f"seg_{state.selected_player_id}_career_bottom", use_container_width=True):
            st.session_state[segment_key] = career_idx
            st.rerun()

    for season_name in sorted(seasons_dict.keys(), reverse=True):
        with st.expander(f"▼ {season_name}", expanded=True):
            profiles = seasons_dict[season_name]
            profiles_sorted = sorted(profiles, key=lambda x: 0 if getattr(x[1], "profile_type", None) == ProfileType.SEASON else 1)

            for (idx, profile) in profiles_sorted:
                is_selected = (st.session_state[segment_key] == idx)
                if getattr(profile, "profile_type", None) == ProfileType.SEASON:
                    btn_label = "⭐ All Competitions"
                else:
                    btn_label = f"   {profile.competition}"

                if is_selected:
                    btn_label = "✅ " + btn_label

                if st.button(btn_label, key=f"seg_{state.selected_player_id}_{idx}_bottom", use_container_width=True):
                    st.session_state[segment_key] = idx
                    st.rerun()
