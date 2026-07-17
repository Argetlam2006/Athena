"""
frontend/components/ask_athena.py — Ask Athena Contextual Drawer.
"""

import streamlit as st

from frontend.data.athena_service import (
    generate_hero_response,
    get_chat_manager,
    get_chat_provider,
    process_athena_turn,
)
from frontend.session import get_state

# Replaced by athena_service


def render_hero_prompt() -> None:
    query = st.chat_input("What deserves my attention today?")

    if query:
        st.session_state.hero_query = query
        st.session_state.hero_response = None

    if st.session_state.get("hero_query"):
        with st.spinner("Athena is thinking..."):
            if not st.session_state.get("hero_response"):
                st.session_state.hero_response = generate_hero_response(
                    st.session_state.hero_query
                )

        st.markdown(
            f"""
            <div style="background: #111827; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #6366f1; margin-bottom: 2rem; margin-top: 1rem;">
                <div style="font-weight: 600; color: #a5b4fc; margin-bottom: 0.75rem; font-size: 0.9rem;">
                    Q: {st.session_state.hero_query}
                </div>
                <div style="color: #e5e7eb; line-height: 1.6;">{st.session_state.hero_response}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_ask_athena_section() -> None:
    manager = get_chat_manager()
    provider = get_chat_provider()
    state = get_state()

    # ─────────────────────────────────────────────────────────────────────────
    # HEADER & BADGES
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown(
        """
    <div style="padding-top: 2rem; padding-bottom: 0.5rem; border-bottom: 1px solid #1f1f1f; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
                <span style="font-size: 1.2rem; color: #6366f1;">◇</span>
                <span style="font-size: 1.1rem; font-weight: 600; color: #f9fafb;">Ask Athena</span>
            </div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    col_badge1, col_badge2, col_btn = st.columns([2, 2, 8])
    with col_badge1:
        st.markdown(
            f"<span style='background: #374151; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; color: #d1d5db;'>Provider: {provider.__class__.__name__}</span>",
            unsafe_allow_html=True,
        )
    with col_badge2:
        st.markdown(
            f"<span style='background: #374151; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; color: #d1d5db;'>Model: {provider.model_name}</span>",
            unsafe_allow_html=True,
        )
    with col_btn:
        if st.button("↺ Clear", help="Clear Conversation", use_container_width=False):
            manager.clear()
            st.rerun()

    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # CONVERSATION HISTORY
    # ─────────────────────────────────────────────────────────────────────────
    chat_container = st.container(height=400)

    with chat_container:
        if not manager.state.messages:
            st.markdown(
                """
            <div style="text-align: center; color: #6b7280; margin-top: 2rem;">
                <div style="font-size: 2rem; margin-bottom: 1rem;">◇</div>
                <div style="font-size: 0.9rem;">I'm Athena. How can I help you analyze this data?</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

        for msg in manager.state.messages:
            if msg.role == "system":
                continue  # Hide internal system transitions

            with st.chat_message(
                msg.role, avatar="🤖" if msg.role == "assistant" else "👤"
            ):
                st.markdown(msg.content)

    # ─────────────────────────────────────────────────────────────────────────
    # INPUT & GENERATION
    # ─────────────────────────────────────────────────────────────────────────
    user_query = st.chat_input("Ask Athena...")

    if user_query:
        # Render user msg instantly
        manager.add_user_message(user_query)
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_query)

            # Render AI thinking state
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analyzing..."):
                    resp_text = process_athena_turn(
                        query=user_query,
                        active_workspace_id=state.active_workspace_id,
                        selected_player_id=state.selected_player_id,
                        selected_team_id=state.selected_team_id,
                    )
                st.markdown(resp_text)
