"""
frontend/theme.py — Visual styling and enterprise dark theme.

Centralizes all CSS and visual styling configurations for the application shell.
"""

import streamlit as st

ATHENA_CSS = """
<style>
/* ── Google Fonts ─────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global reset ─────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Streamlit chrome ─────────────────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background-color: #0a0a0a;
}
[data-testid="stHeader"] {
    background-color: #0a0a0a;
    border-bottom: 1px solid #1a1a1a;
}
[data-testid="stSidebar"] {
    background-color: #0d0d0d;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }

/* ── Typography ───────────────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif;
    color: #f0f0f0;
    letter-spacing: -0.02em;
}
p, li, span {
    color: #9ca3af;
    line-height: 1.6;
}

/* ── Divider ──────────────────────────────────────────────────── */
.athena-divider {
    border: none;
    border-top: 1px solid #1f1f1f;
    margin: 2rem 0;
}

/* ── Custom Utilities ─────────────────────────────────────────── */
.section-label {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    color: #4b5563;
    text-transform: uppercase;
    margin-bottom: 1.25rem;
}

.notice-banner {
    background: rgba(99, 102, 241, 0.06);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 8px;
    padding: 1rem 1.25rem;
    font-size: 0.82rem;
    color: #818cf8;
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
}

/* ── Reusable Component Containers ────────────────────────────── */
.card-container {
    background: #111111;
    border: 1px solid #1f1f1f;
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
}
</style>
"""

def load_theme():
    """Injects the Athena enterprise theme CSS into the Streamlit app."""
    st.markdown(ATHENA_CSS, unsafe_allow_html=True)
