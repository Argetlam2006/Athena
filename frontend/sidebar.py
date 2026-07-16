"""
frontend/sidebar.py — Global persistent sidebar.

Renders navigation, context selectors, system status, and the Ask Athena placeholder.
Directly reads from and writes to the centralized session state.
"""

import streamlit as st

from frontend.session import (
    get_state,
    set_active_workspace,
)
from shared.config.navigation import WORKSPACES


def render_workspace_navigation() -> None:
    """Renders dynamic workspace links based on config."""
    state = get_state()

    st.markdown(
        "<div style='margin-bottom: 1rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>Intelligence Workspaces</div>",
        unsafe_allow_html=True,
    )

    for workspace in WORKSPACES:
        if workspace.status == "live":
            is_active = state.active_workspace_id == workspace.id
            btn_key = f"nav_{workspace.id}"

            if is_active:
                st.markdown(f"**{workspace.icon} {workspace.name}**")
            else:
                if st.button(
                    f"{workspace.icon} {workspace.name}",
                    key=btn_key,
                    use_container_width=True,
                ):
                    set_active_workspace(workspace.id)
                    st.rerun()


def render_context_selectors() -> None:
    """Renders global player and team selectors."""
    # Global Context removed as per Phase 11A.1
    # Search now happens inside the relevant workspace
    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)


def render_system_status() -> None:
    """Renders the system status indicator."""
    st.markdown(
        "<div style='margin-top: 2rem; margin-bottom: 0.5rem; color: #4b5563; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; letter-spacing: 0.1em;'>System Status</div>",
        unsafe_allow_html=True,
    )

    # Mocking status check
    st.markdown(
        """
    <div style="font-size: 0.8rem; color: #10b981; display: flex; align-items: center; gap: 0.5rem;">
        ● <span>Data Warehouse Online</span>
    </div>
    <div style="font-size: 0.8rem; color: #10b981; display: flex; align-items: center; gap: 0.5rem; margin-top: 0.2rem;">
        ● <span>Intelligence Engine Ready</span>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_global_sidebar() -> None:
    """Assembles and renders the complete global sidebar."""
    with st.sidebar:
        st.markdown(
            """
        <div style="margin-bottom: 2rem;">
            <div style="font-size: 0.75rem; font-weight: 600; letter-spacing: 0.25em; color: #6366f1; text-transform: uppercase;">Athena</div>
            <div style="font-size: 1.25rem; font-weight: 700; color: #f9fafb;">Decision Engine</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        render_workspace_navigation()
        render_context_selectors()

        st.markdown(
            "<div style='flex-grow: 1; height: 100px;'></div>", unsafe_allow_html=True
        )
        render_system_status()
