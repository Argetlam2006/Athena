"""
frontend/layout.py — Generic structural layout primitives.

Provides reusable layout wrappers to enforce consistent spacing, typography,
and structural patterns across all workspaces. No domain logic here.
"""

import streamlit as st


def render_page_header(title: str, subtitle: str, icon: str = "") -> None:
    """Renders a standard workspace header."""
    icon_html = f'<span style="color:#6366f1; margin-right:10px;">{icon}</span>' if icon else ""
    st.markdown(f"""
    <div style="padding: 1rem 0 2rem 0; border-bottom: 1px solid #1f1f1f; margin-bottom: 2rem;">
        <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700; color: #f9fafb;">
            {icon_html}{title}
        </h1>
        <p style="margin: 0.5rem 0 0 0; color: #9ca3af; font-size: 1.05rem;">
            {subtitle}
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_section_header(title: str) -> None:
    """Renders a standard uppercase section label."""
    st.markdown(f"<div class='section-label'>{title}</div>", unsafe_allow_html=True)


def render_kpi_card(label: str, value: str | int | float, delta: str | None = None) -> None:
    """Renders a standard KPI card inside a unified container."""
    delta_html = f'<div style="font-size: 0.8rem; color: #10b981; margin-top: 0.4rem;">↑ {delta}</div>' if delta else ""
    st.markdown(f"""
    <div class="card-container">
        <div style="font-size: 2rem; font-weight: 700; color: #f9fafb; line-height: 1; margin-bottom: 0.25rem;">
            {value}
        </div>
        <div style="font-size: 0.75rem; color: #4b5563; font-weight: 500; text-transform: uppercase; letter-spacing: 0.08em;">
            {label}
        </div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def render_divider() -> None:
    """Renders a standard section divider."""
    st.markdown("<div class='athena-divider'></div>", unsafe_allow_html=True)
