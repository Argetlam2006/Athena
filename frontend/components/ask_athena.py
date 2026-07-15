"""
frontend/components/ask_athena.py — Ask Athena Drawer.

Placeholder UI shell for the future AI integration.
"""

import streamlit as st


def render_ask_athena_drawer() -> None:
    """
    Renders the Ask Athena drawer or placeholder.
    In the final system, this will be an off-canvas chat interface.
    For now, it's a fixed component.
    """
    st.markdown("""
    <div style="background: #111111; border: 1px solid #374151; border-radius: 8px; padding: 1.5rem; margin-top: 2rem;">
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
            <span style="font-size: 1.5rem; color: #6366f1;">◇</span>
            <span style="font-size: 1.1rem; font-weight: 600; color: #e5e7eb;">Ask Athena</span>
        </div>
        <div style="color: #9ca3af; font-size: 0.9rem; line-height: 1.5; margin-bottom: 1rem;">
            The conversational AI layer is currently offline. When activated, Athena will be able to answer natural language queries grounded in the intelligence engine's output.
        </div>
        <input type="text" disabled placeholder="Message Athena..." 
               style="width: 100%; padding: 0.75rem; background: #1a1a1a; border: 1px solid #374151; border-radius: 4px; color: #6b7280; font-size: 0.85rem;" />
    </div>
    """, unsafe_allow_html=True)
