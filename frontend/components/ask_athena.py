"""
frontend/components/ask_athena.py — Ask Athena Contextual Drawer.
"""

import time

import streamlit as st

from backend.explanation.conversation import ConversationManager
from backend.explanation.engine import ExplanationContextEngine
from backend.explanation.prompt_builder import PromptBuilder
from backend.explanation.providers.factory import get_provider
from backend.explanation.telemetry import ExplanationTelemetry, record_telemetry
from frontend.data.players import get_player_profile
from frontend.data.teams import get_team_profile
from frontend.session import get_state
from shared.config.settings import settings


def _init_chat_state():
    if "chat_manager" not in st.session_state:
        st.session_state.chat_manager = ConversationManager()
    if "chat_provider" not in st.session_state:
        st.session_state.chat_provider = get_provider(settings.ATHENA_PROVIDER)


def _get_context_for_prompt():
    """Builds the actual context object based on active UI state."""
    state = get_state()
    engine = ExplanationContextEngine()

    if state.active_workspace_id == "player_intelligence" and state.selected_player_id:
        p = get_player_profile(state.selected_player_id)
        if p:
            return engine.get_player_context(p), "player"

    if state.active_workspace_id == "team_intelligence" and state.selected_team_id:
        t = get_team_profile(state.selected_team_id)
        if t:
            return engine.get_team_context(t), "team"

    # For now, default to empty context or None if no specific context
    return None, "general"


def render_ask_athena_drawer() -> None:
    _init_chat_state()
    manager: ConversationManager = st.session_state.chat_manager
    provider = st.session_state.chat_provider
    state = get_state()

    # Check for context shifts
    manager.detect_and_handle_context_change(
        state.selected_player_id, state.selected_team_id, state.active_workspace_id
    )

    # ─────────────────────────────────────────────────────────────────────────
    # HEADER & BADGES
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown(
        """
    <div style="padding-bottom: 0.5rem; border-bottom: 1px solid #1f1f1f; margin-bottom: 1rem;">
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

    col_badge1, col_badge2, col_btn = st.columns([2, 2, 1])
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
        if st.button("↺", help="Clear Conversation", use_container_width=True):
            manager.clear()
            st.rerun()

    st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # CONVERSATION HISTORY
    # ─────────────────────────────────────────────────────────────────────────
    chat_container = st.container(height=500)

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
                # Get Context & Build Prompt
                ctx_obj, ctx_type = _get_context_for_prompt()

                if ctx_obj:
                    pb = PromptBuilder()
                    prompt_pkg = pb.build(user_query, ctx_obj, ctx_type)

                    # Stream response
                    start_stream = time.time()
                    try:
                        stream = provider.stream(prompt_pkg)
                        response_text = st.write_stream(stream)
                        stream_dur = (time.time() - start_stream) * 1000

                        manager.add_assistant_message(response_text)

                        # Telemetry
                        record_telemetry(
                            ExplanationTelemetry(
                                provider=provider.__class__.__name__.replace(
                                    "Provider", ""
                                ).lower(),
                                model=provider.model_name,
                                prompt_version=prompt_pkg.prompt_version,
                                context_size_bytes=prompt_pkg.metadata[
                                    "context_size_bytes"
                                ],
                                latency_ms=stream_dur,
                                streaming_duration_ms=stream_dur,
                                tokens_prompt=len(prompt_pkg.serialized_context) // 4,
                                tokens_completion=len(response_text) // 4,
                                status="success",
                            )
                        )

                        # Evidence Expandable
                        with st.expander("Evidence Used"):
                            st.json(ctx_obj)

                    except Exception as e:
                        st.error(f"Provider Error: {str(e)}")
                        record_telemetry(
                            ExplanationTelemetry(
                                provider=provider.__class__.__name__.lower(),
                                model=provider.model_name,
                                prompt_version="unknown",
                                context_size_bytes=0,
                                latency_ms=0,
                                streaming_duration_ms=0,
                                tokens_prompt=0,
                                tokens_completion=0,
                                status="error",
                                error_message=str(e),
                            )
                        )
                else:
                    st.info(
                        "I don't have enough structured context in this workspace to answer that yet."
                    )
                    manager.add_assistant_message(
                        "I don't have enough structured context in this workspace to answer that yet."
                    )
