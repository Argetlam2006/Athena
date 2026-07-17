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

    from frontend.data.player_service import get_player_decision_card

    with st.spinner("Analyzing player profile..."):
        card = get_player_decision_card(player)

    def render_cap_explanation(exp):
        drivers_html = "".join(
            [f"<li><strong>{k}:</strong> {v}</li>" for k, v in exp.drivers.items()]
        )
        return f"""<div style="margin-bottom: 0.5rem;">
<strong style="color: #f9fafb;">{exp.capability_name} ({exp.score})</strong>
<ul style="margin: 0; padding-left: 1.2rem; color: #9ca3af; font-size: 0.85rem;">
{drivers_html}
</ul>
</div>"""

    elite_html = (
        "".join([render_cap_explanation(e) for e in card.elite_traits])
        if card.elite_traits
        else "<p style='color: #9ca3af; font-size: 0.9rem;'>No elite outliers identified against positional peers.</p>"
    )
    weak_html = (
        "".join([render_cap_explanation(w) for w in card.weak_areas])
        if card.weak_areas
        else "<p style='color: #9ca3af; font-size: 0.9rem;'>No significant weaknesses against positional peers.</p>"
    )

    summary = f"""<div class="card-container" style="background: rgba(99, 102, 241, 0.05); border-color: rgba(99, 102, 241, 0.2);">
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
</div>"""
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

    from frontend.data.player_service import get_player_career

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

    career_idx = next(
        (
            i
            for i, p in enumerate(career)
            if getattr(p, "profile_type", None) == ProfileType.CAREER
            or p.season == "Career"
        ),
        -1,
    )

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
    col1, col_arch = st.columns([2, 1])
    with col1:
        # Construct header metadata without placeholders
        metadata_parts = []
        if (
            getattr(player, "profile_type", None) == ProfileType.CAREER
            or player.season == "Career"
        ):
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
            f"""<h2 style="margin: 0; color: #f9fafb;">{player.player_name}</h2>
<div style="color: #9ca3af; font-size: 1.1rem; margin-bottom: 1rem;">
{metadata_str}
<span style="font-size: 0.8rem; background: #374151; padding: 0.1rem 0.5rem; border-radius: 4px; margin-left: 0.5rem;">Dataset Context: Latest available season {player.season}</span>
</div>""",
            unsafe_allow_html=True,
        )
    with col_arch:
        st.markdown(
            f"""<div style="background: rgba(30, 41, 59, 0.5); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); text-align: center;">
<div style="font-size: 0.75rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Playing Style</div>
<div style="font-size: 1.2rem; font-weight: 600; color: #818cf8;">{player.display_archetype}</div>
<div style="font-size: 0.85rem; color: #6b7280;">{player.archetype_description}</div>
</div>""",
            unsafe_allow_html=True,
        )

        from backend.intelligence.roles import get_role_family

        role_family = get_role_family(player.display_archetype)
        st.markdown(
            f"""<div style="margin-top: 0.5rem; background: rgba(30, 41, 59, 0.5); padding: 1rem; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); text-align: center;">
<div style="font-size: 0.75rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">Role Family</div>
<div style="font-size: 1.1rem; font-weight: 600; color: #10b981;">{role_family}</div>
</div>""",
            unsafe_allow_html=True,
        )

    render_divider()

    # Player Header Stats
    fv = player.feature_vector
    if fv:
        st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
        raw = fv.raw_metrics or {}
        header_stats = {
            "Matches": fv.matches_played,
            "Minutes": int(fv.minutes_played)
            if fv.minutes_played is not None
            else None,
        }

        if "goals" in raw:
            header_stats["Goals"] = raw["goals"]
        if "goal_assists" in raw:
            header_stats["Assists"] = raw["goal_assists"]

        header_stats["Goals p90"] = (
            f"{fv.goals_p90:.2f}" if fv.goals_p90 is not None else None
        )
        header_stats["Assists p90"] = (
            f"{fv.goal_assists_p90:.2f}" if fv.goal_assists_p90 is not None else None
        )

        metrics = {k: v for k, v in header_stats.items() if v is not None}

        cols = st.columns(len(metrics))
        for i, (label, val) in enumerate(metrics.items()):
            with cols[i]:
                st.markdown(
                    f"""<div style="background: #1f2937; padding: 1rem; border-radius: 8px; border: 1px solid #374151; text-align: center;">
<div style="color: #9ca3af; font-size: 0.8rem; margin-bottom: 0.25rem;">{label}</div>
<div style="color: #f9fafb; font-size: 1.25rem; font-weight: 600;">{val}</div>
</div>""",
                    unsafe_allow_html=True,
                )

    render_divider()

    # Dynamic Player Statistics
    if fv:
        if role_family == "Goalkeeper":
            category = "Goalkeeper"
        elif role_family in ["Progressive Defender", "Traditional Defender"]:
            category = "Defender"
        elif role_family in ["Midfield Controller", "Midfield Destroyer"]:
            category = "Midfielder"
        elif role_family in ["Creative Attacker", "Goal Scorer"]:
            category = "Attacker"
        else:
            pos = player.position_group.lower() if player.position_group else ""
            if "goalkeeper" in pos:
                category = "Goalkeeper"
            elif "back" in pos or "defender" in pos:
                category = "Defender"
            elif "mid" in pos:
                category = "Midfielder"
            else:
                category = "Attacker"

        render_section_header(f"{category} Statistics")
        st.markdown(
            "<p style='color: #9ca3af; font-size: 0.9rem; margin-bottom: 1.5rem;'>Raw primitive metrics feeding the Intelligence Engine (Per 90).</p>",
            unsafe_allow_html=True,
        )

        def render_stat_group(title: str, stats: dict[str, float | None]):
            valid_stats = {k: v for k, v in stats.items() if v is not None}
            if not valid_stats:
                return
            st.markdown(f"#### {title}")
            scols = st.columns(max(len(valid_stats), 1))
            for i, (label, val) in enumerate(valid_stats.items()):
                with scols[i % len(scols)]:
                    st.markdown(
                        f"""<div style="border-left: 2px solid #4f46e5; padding-left: 0.75rem; margin-bottom: 1rem;">
<div style="color: #9ca3af; font-size: 0.75rem; text-transform: uppercase;">{label}</div>
<div style="color: #e5e7eb; font-size: 1.1rem; font-weight: 500;">{val:.2f}</div>
</div>""",
                        unsafe_allow_html=True,
                    )
            st.markdown(
                "<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True
            )

        if category != "Goalkeeper":
            if category in ["Attacker", "Midfielder"]:
                render_stat_group(
                    "Attacking Threat",
                    {
                        "Goals": fv.goals_p90,
                        "NPxG": fv.npxg_p90,
                        "Shot Accuracy %": fv.shot_accuracy_pct,
                        "Goals - xG": fv.goals_minus_xg,
                    },
                )
                render_stat_group(
                    "Chance Creation",
                    {
                        "Assists": fv.goal_assists_p90,
                        "Shot Assists": fv.shot_assists_p90,
                        "Through Balls": fv.through_balls_p90,
                        "Crosses": fv.crosses_p90,
                    },
                )

            if category in ["Attacker", "Midfielder", "Defender"]:
                render_stat_group(
                    "Ball Progression",
                    {
                        "Progressive Passes": fv.progressive_passes_p90,
                        "Progressive Carries": fv.progressive_carries_p90,
                        "Carry Distance": fv.carry_distance_p90,
                        "Switches": fv.switches_p90,
                    },
                )

            if category in ["Midfielder", "Defender"]:
                render_stat_group(
                    "Ball Security",
                    {
                        "Pass Accuracy %": fv.pass_accuracy_pct,
                        "Dribble Success %": fv.dribble_success_pct,
                        "Total Passes": fv.passes_p90,
                        "Avg Pass Length": fv.avg_pass_length_m,
                    },
                )
                render_stat_group(
                    "Press Resistance",
                    {
                        "Pressure %": fv.pressure_pct,
                        "Events Under Pressure": fv.events_under_pressure_p90,
                    },
                )

            if category in ["Defender", "Midfielder", "Attacker"]:
                render_stat_group(
                    "Defensive Activity",
                    {
                        "Pressures": fv.pressures_p90,
                        "Recoveries": fv.recoveries_p90,
                        "Interceptions": fv.interceptions_p90,
                        "Tackles": fv.tackles_p90,
                        "Tackles Won": fv.tackles_won_p90,
                        "Clearances": fv.clearances_p90,
                        "Aerial Win %": (
                            fv.aerials_won_p90 / fv.aerials_total_p90 * 100
                        )
                        if getattr(fv, "aerials_total_p90", 0)
                        else 0.0,
                        "Dribbled Past": fv.dribbled_past_p90,
                        "Errors -> Shot": fv.errors_leading_to_shot_p90,
                    },
                )
        else:
            st.info("No advanced metrics available for Goalkeepers in current dataset.")

    render_divider()

    # Render Strengths/Weaknesses if Career Overview
    cap = player.capability_profile
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
                    st.markdown(
                        f"- ✅ <span style='color: #10b981;'>{s}</span>",
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("No significant deterministic strengths identified.")

        with c2:
            st.markdown("#### Weaknesses")
            if weaknesses:
                for w in weaknesses:
                    st.markdown(
                        f"- ⚠️ <span style='color: #ef4444;'>{w}</span>",
                        unsafe_allow_html=True,
                    )
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
            cap_data = player.capability_profile.as_radar_dict()
            import altair as alt
            import pandas as pd

            cap_df = pd.DataFrame(
                list(cap_data.items()), columns=["Capability", "Score"]
            )

            bars = (
                alt.Chart(cap_df)
                .mark_bar(
                    color="#6366f1", cornerRadiusTopLeft=4, cornerRadiusTopRight=4
                )
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
    st.markdown(
        "<p style='color: #9ca3af; font-size: 0.9rem;'>Select a specific club and season context to drill down into the profile.</p>",
        unsafe_allow_html=True,
    )

    # Render Career Overview Button
    if career_idx != -1:
        is_career_selected = st.session_state[segment_key] == career_idx
        btn_label = "✅ Career Overview" if is_career_selected else "Career Overview"
        if st.button(
            btn_label,
            key=f"seg_{state.selected_player_id}_career_bottom",
            use_container_width=True,
        ):
            st.session_state[segment_key] = career_idx
            st.rerun()

    for season_name in sorted(seasons_dict.keys(), reverse=True):
        with st.expander(f"▼ {season_name}", expanded=True):
            profiles = seasons_dict[season_name]
            profiles_sorted = sorted(
                profiles,
                key=lambda x: (
                    0
                    if getattr(x[1], "profile_type", None) == ProfileType.SEASON
                    else 1
                ),
            )

            for idx, profile in profiles_sorted:
                is_selected = st.session_state[segment_key] == idx
                if getattr(profile, "profile_type", None) == ProfileType.SEASON:
                    btn_label = "⭐ All Competitions"
                else:
                    btn_label = f"   {profile.competition}"

                if is_selected:
                    btn_label = "✅ " + btn_label

                if st.button(
                    btn_label,
                    key=f"seg_{state.selected_player_id}_{idx}_bottom",
                    use_container_width=True,
                ):
                    st.session_state[segment_key] = idx
                    st.rerun()
