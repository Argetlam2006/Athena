"""
frontend/pages/player_intelligence.py — Player Intelligence Workspace.
"""

import streamlit as st
from frontend.session import get_state
from frontend.data.players import get_player_profile
from frontend.layout import render_page_header, render_section_header, render_divider
from frontend.components.states import render_empty_state


def render_scout_summary(player) -> None:
    """Generates a deterministic text summary without an LLM."""
    if not player.capability_profile:
        return
        
    cap = player.capability_profile
    def score(name):
        val = getattr(cap, name)
        return val.score if val else 0.0

    # Deterministic logic
    strengths = []
    weaknesses = []
    for cap_name in ["ball_progression", "chance_creation", "ball_security", "press_resistance", "defensive_activity", "attacking_threat"]:
        s = score(cap_name)
        display_name = cap_name.replace("_", " ").title()
        if s >= 80:
            strengths.append(display_name)
        elif s < 45:
            weaknesses.append(display_name)

    style = "balanced"
    if score("attacking_threat") > 75 and score("defensive_activity") < 50:
        style = "attack-minded"
    elif score("defensive_activity") > 75 and score("attacking_threat") < 50:
        style = "defense-minded"
        
    concerns = "None"
    if score("physical_availability") < 60:
        concerns = "Availability history suggests elevated injury risk."
    elif len(weaknesses) > 2:
        concerns = "Notable gaps in multiple core capabilities."

    summary = f"""
    <div class="card-container" style="background: rgba(99, 102, 241, 0.05); border-color: rgba(99, 102, 241, 0.2);">
        <p style="margin-top: 0; color: #e5e7eb; line-height: 1.6;">
            <strong>{player.player_name}</strong> operates as a <strong>{player.archetype}</strong>, featuring a predominantly <em>{style}</em> profile. 
            They provide elite output in <strong>{', '.join(strengths) if strengths else 'several areas'}</strong>.
        </p>
        <p style="color: #9ca3af; margin-bottom: 0;">
            <strong>Key Concern:</strong> {concerns}
        </p>
    </div>
    """
    st.markdown(summary, unsafe_allow_html=True)


def render() -> None:
    render_page_header("Player Intelligence", "What kind of player is this?", "◈")
    
    state = get_state()
    if not state.selected_player_id:
        render_empty_state("◈", "No Player Selected", "Please select a focus player from the global context menu in the sidebar to view their intelligence profile.")
        return
        
    player = get_player_profile(state.selected_player_id)
    if not player:
        render_empty_state("⚠", "Player Not Found", "The selected player could not be found in the database.")
        return
        
    # Main Profile Header
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"""
        <h2 style="margin: 0; color: #f9fafb;">{player.player_name}</h2>
        <div style="color: #9ca3af; font-size: 1.1rem; margin-bottom: 1rem;">
            {player.position_group} • {player.team_name} • {player.age_years} yrs
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if player.archetype:
            st.markdown(f"""
            <div style="text-align: right;">
                <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: #4b5563;">Role Classification</div>
                <div style="font-size: 1.2rem; font-weight: 600; color: #818cf8;">{player.archetype}</div>
                <div style="font-size: 0.85rem; color: #6b7280;">{player.archetype_description}</div>
            </div>
            """, unsafe_allow_html=True)
            
    render_divider()
    
    # Scout Summary
    render_section_header("Deterministic Scout Summary")
    render_scout_summary(player)
    
    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
    
    col_cap, col_sig = st.columns([2, 1])
    with col_cap:
        render_section_header("Capability Profile")
        if player.capability_profile:
            # We would render a real radar chart here with Plotly or Altair.
            # For the structural phase, we render the raw bars.
            cap = player.capability_profile
            for metric in ["ball_progression", "chance_creation", "ball_security", "press_resistance", "defensive_activity", "attacking_threat", "physical_availability", "tactical_versatility"]:
                val_obj = getattr(cap, metric)
                if val_obj:
                    score = val_obj.score
                    name = metric.replace("_", " ").title()
                    # A simple CSS bar
                    st.markdown(f"""
                    <div style="margin-bottom: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.25rem;">
                            <span style="color: #d1d5db;">{name}</span>
                            <span style="color: #9ca3af; font-weight: 600;">{score:.1f}</span>
                        </div>
                        <div style="width: 100%; background-color: #1f2937; border-radius: 4px; height: 8px;">
                            <div style="width: {score}%; background-color: {'#10b981' if score >= 75 else '#3b82f6' if score >= 50 else '#ef4444'}; height: 100%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Capability profile not generated.")
            
    with col_sig:
        render_section_header("Decision Signals")
        if player.decision_signals:
            for sig in player.decision_signals:
                st.markdown(f"""
                <div style="background: #111827; border-left: 3px solid #6366f1; padding: 0.75rem 1rem; margin-bottom: 0.5rem; font-size: 0.9rem; color: #e5e7eb;">
                    {sig.replace('_', ' ').title()}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='color: #6b7280; font-size: 0.9rem;'>No active signals.</div>", unsafe_allow_html=True)
