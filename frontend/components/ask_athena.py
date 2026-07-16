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
from frontend.data.teams import get_team_profile
from frontend.session import get_state
from shared.config.settings import settings


def _init_chat_state():
    if "chat_manager" not in st.session_state:
        st.session_state.chat_manager = ConversationManager()
    if "chat_provider" not in st.session_state:
        st.session_state.chat_provider = get_provider(settings.ATHENA_PROVIDER)


def _get_context_for_prompt(query: str = ""):
    """Builds the actual context object based on active UI state and query intent."""
    state = get_state()
    engine = ExplanationContextEngine()

    if state.active_workspace_id == "player_intelligence" and state.selected_player_id:
        from frontend.data.players import get_player_career
        career = get_player_career(state.selected_player_id)

        if career:
            q_lower = query.lower()

            from shared.schemas import ProfileType

            # Simple heuristic intent parser
            is_compare = "compare" in q_lower
            is_career_summary = any(w in q_lower for w in ["career", "summarise", "summarize", "overview"]) and "season" not in q_lower
            is_competition_specific = any(c.lower() in q_lower for c in {p.competition for p in career if p.profile_type == ProfileType.COMPETITION})

            filtered_profiles = []

            if is_competition_specific:
                # E.g. "How did Messi perform in La Liga?"
                mentioned_comps = [c for c in {p.competition for p in career if p.profile_type == ProfileType.COMPETITION} if c.lower() in q_lower]
                filtered_profiles = [p for p in career if p.competition in mentioned_comps and p.profile_type == ProfileType.COMPETITION]

            elif is_compare:
                # E.g. "compare 2011 and 2015"
                # Check if season string exists in query
                filtered_profiles = [p for p in career if p.profile_type == ProfileType.SEASON and any(part in q_lower for part in p.season.split('/'))]

            elif is_career_summary:
                # E.g. "Summarise Messi's career"
                filtered_profiles = [p for p in career if p.profile_type == ProfileType.CAREER]

            else:
                # Default: Career + all Season profiles
                filtered_profiles = [p for p in career if p.profile_type in [ProfileType.CAREER, ProfileType.SEASON]]

            if not filtered_profiles:
                # Fallback to Career Profile if nothing matches specifically
                career_prof = next((p for p in career if p.profile_type == ProfileType.CAREER), None)
                if career_prof:
                    filtered_profiles = [career_prof]
                else:
                    filtered_profiles = [career[0]]

            # Build contexts
            contexts = [engine.get_player_context(p) for p in filtered_profiles]

            # If multiple, return the list (ContextFormatter handles it). If single, return single.
            if len(contexts) == 1:
                return contexts[0], "player"
            return contexts, "player_multi"

    if state.active_workspace_id == "team_intelligence" and state.selected_team_id:
        t = get_team_profile(state.selected_team_id)
        if t:
            return engine.get_team_context(t), "team"

    # For now, default to empty context or None if no specific context
    return None, "general"

def render_hero_prompt() -> None:
    _init_chat_state()
    provider = st.session_state.chat_provider

    query = st.chat_input("What deserves my attention today?")

    if query:
        st.session_state.hero_query = query
        st.session_state.hero_response = None

    if st.session_state.get("hero_query"):
        with st.spinner("Athena is thinking..."):
            if not st.session_state.get("hero_response"):
                from backend.explanation.prompt_builder import PromptBuilder

                builder = PromptBuilder()
                prompt_pkg = builder.build(st.session_state.hero_query, None, "general")
                try:
                    resp = provider.generate(prompt_pkg)
                    st.session_state.hero_response = resp.generated_text
                except Exception as e:
                    st.session_state.hero_response = f"An error occurred: {e}"

        st.markdown(
            f"""
            <div style="background: #111827; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #6366f1; margin-bottom: 2rem; margin-top: 1rem;">
                <div style="font-weight: 600; color: #a5b4fc; margin-bottom: 0.75rem; font-size: 0.9rem;">
                    Q: {st.session_state.hero_query}
                </div>
                <div style="color: #e5e7eb; line-height: 1.6;">{st.session_state.hero_response}</div>
            </div>
            """, unsafe_allow_html=True
        )


def render_ask_athena_section() -> None:
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
                # Get Context & Build Prompt
                ctx_obj, ctx_type = _get_context_for_prompt(user_query)

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
                    if ctx_obj:
                        with st.expander("Evidence Used"):
                            # Determine scope & reason
                            reason = "Explicit Context"
                            scope = "Single Season"
                            if ctx_type == "compare":
                                reason = "Compare Intent Detected"
                                scope = "Multi-Season / Multi-Player"
                            elif ctx_type == "career":
                                reason = "Career Intent Detected"
                                scope = "Aggregate Career"
                            elif isinstance(ctx_obj, list):
                                reason = "Multi-Season Intent Detected"
                                scope = "Historical Collection"

                            st.markdown(
                                f"""
                                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; font-size: 0.9rem;">
                                    <div><span style="color: #9ca3af;">Context Type:</span> {ctx_type.capitalize()}</div>
                                    <div><span style="color: #9ca3af;">Evidence Scope:</span> {scope}</div>
                                    <div style="grid-column: 1 / -1;"><span style="color: #9ca3af;">Reason for Retrieval:</span> {reason}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            st.markdown("##### Retrieved Profiles")
                            if isinstance(ctx_obj, list):
                                for c in ctx_obj:
                                    st.markdown(f"- **{c.player_name}** ({c.season}) - {c.team_name}")
                            else:
                                entity_name = getattr(ctx_obj, 'player_name', getattr(ctx_obj, 'team_name', 'Unknown'))
                                season_str = getattr(ctx_obj, 'season', '')
                                st.markdown(f"- **{entity_name}** {season_str}")

                            with st.expander("Raw JSON (Debug)"):
                                if isinstance(ctx_obj, list):
                                    st.json([c.model_dump() for c in ctx_obj])
                                else:
                                    st.json(ctx_obj.model_dump())

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
