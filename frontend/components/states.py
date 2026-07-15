"""
frontend/components/states.py — UI State Components.

Reusable frontend components for Loading, Empty, and Error states.
"""

import streamlit as st


def render_loading_state(message: str = "Loading data...") -> None:
    """Renders a unified loading state."""
    with st.spinner(message):
        # We also yield a small placeholder so layout doesn't completely collapse
        st.markdown("<div style='height: 100px;'></div>", unsafe_allow_html=True)


def render_empty_state(icon: str, title: str, description: str, suggestion: str = "") -> None:
    """Renders a professional empty state."""
    suggestion_html = f'<div style="margin-top: 1rem; font-size: 0.85rem; color: #818cf8;">{suggestion}</div>' if suggestion else ""
    st.markdown(f"""
    <div style="text-align: center; padding: 4rem 2rem; border: 1px dashed #1f1f1f; border-radius: 8px; background: #0d0d0d;">
        <div style="font-size: 2.5rem; color: #374151; margin-bottom: 1rem;">{icon}</div>
        <div style="font-size: 1.1rem; font-weight: 600; color: #e5e7eb; margin-bottom: 0.5rem;">{title}</div>
        <div style="font-size: 0.9rem; color: #6b7280; max-width: 400px; margin: 0 auto;">{description}</div>
        {suggestion_html}
    </div>
    """, unsafe_allow_html=True)


def render_error_state(title: str, error_details: str) -> None:
    """Renders a non-intrusive error banner."""
    st.markdown(f"""
    <div style="background: rgba(239, 68, 68, 0.05); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 8px; padding: 1.25rem;">
        <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem;">
            <span style="color: #ef4444; font-size: 1.2rem;">⚠</span>
            <strong style="color: #fca5a5; font-size: 0.95rem;">{title}</strong>
        </div>
        <div style="color: #94a3b8; font-size: 0.85rem; margin-left: 2rem;">
            {error_details}
        </div>
    </div>
    """, unsafe_allow_html=True)
