"""
frontend/components/ask_athena.py — Ask Athena Contextual Drawer.

Provides the persistent conversation UI for interacting with Athena.
"""

import streamlit as st
from frontend.session import get_state
from frontend.data.players import get_player_profile
from frontend.data.teams import get_team_profile

def render_ask_athena_drawer() -> None:
    """
    Renders the contextual AI assistant drawer.
    """
    st.markdown("""
    <div style="padding-bottom: 1rem; border-bottom: 1px solid #1f1f1f; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.2rem; color: #6366f1;">◇</span>
            <span style="font-size: 1.1rem; font-weight: 600; color: #f9fafb;">Ask Athena</span>
        </div>
        <div style="font-size: 0.8rem; color: #9ca3af; margin-top: 0.25rem;">Contextual Intelligence Assistant</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 1. Context Summary
    state = get_state()
    ctx_parts = []
    ctx_parts.append(f"Workspace: {state.active_workspace_id.replace('_', ' ').title()}")
    
    if state.selected_player_id:
        p = get_player_profile(state.selected_player_id)
        if p:
            ctx_parts.append(f"Player: {p.player_name}")
            
    if state.selected_team_id:
        t = get_team_profile(state.selected_team_id)
        if t:
            ctx_parts.append(f"Team: {t.team_name}")
            
    st.markdown("<div style='font-size: 0.75rem; font-weight: 600; color: #4b5563; text-transform: uppercase; margin-bottom: 0.5rem;'>Current Context</div>", unsafe_allow_html=True)
    for ctx in ctx_parts:
        st.markdown(f"<div style='font-size: 0.85rem; color: #818cf8; margin-bottom: 0.25rem;'>• {ctx}</div>", unsafe_allow_html=True)
        
    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)
    
    # 2. Conversation Layout (Placeholder history)
    st.markdown("<div style='font-size: 0.75rem; font-weight: 600; color: #4b5563; text-transform: uppercase; margin-bottom: 0.5rem;'>Conversation</div>", unsafe_allow_html=True)
    
    # AI Message
    st.markdown("""
    <div style="background: rgba(99, 102, 241, 0.1); border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
        <div style="font-size: 0.75rem; font-weight: 600; color: #818cf8; margin-bottom: 0.25rem;">ATHENA</div>
        <div style="font-size: 0.9rem; color: #e5e7eb; line-height: 1.5;">I am currently in structural preview mode. I can see your context but my intelligence engine is not yet connected.</div>
    </div>
    """, unsafe_allow_html=True)
    
    # User Message Placeholder
    st.markdown("""
    <div style="background: #1f2937; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; margin-left: 1rem;">
        <div style="font-size: 0.75rem; font-weight: 600; color: #9ca3af; margin-bottom: 0.25rem;">YOU</div>
        <div style="font-size: 0.9rem; color: #d1d5db; line-height: 1.5;">How does this player compare to the league average?</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Evidence Panel Placeholder
    with st.expander("View Evidence Matrix", expanded=False):
        st.markdown("<div style='font-size: 0.8rem; color: #9ca3af;'>No structured evidence available for this interaction.</div>", unsafe_allow_html=True)
    
    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)
    
    # 3. Prompt Input
    st.text_input("Ask Athena", placeholder="Message Athena...", label_visibility="collapsed", disabled=True)
