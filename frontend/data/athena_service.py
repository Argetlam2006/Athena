"""
frontend/data/athena_service.py — Frontend Data Service for Ask Athena.

Coordinates data access and intelligence algorithms for LLM interactions.
"""

import streamlit as st

from backend.explanation.conversation import ConversationManager
from backend.explanation.engine import ExplanationContextEngine
from backend.explanation.intent import ConversationIntent, IntentClassifier
from backend.explanation.prompt_builder import PromptBuilder
from backend.explanation.providers.factory import get_provider
from backend.explanation.telemetry import record_telemetry
from frontend.data.player_service import get_player_career
from frontend.data.team_service import get_collective_profile
from shared.config.settings import settings


def init_chat_state():
    if "chat_manager" not in st.session_state:
        st.session_state.chat_manager = ConversationManager()
    if "chat_provider" not in st.session_state:
        st.session_state.chat_provider = get_provider(settings.ATHENA_PROVIDER)


def get_chat_manager() -> ConversationManager:
    init_chat_state()
    return st.session_state.chat_manager


def get_chat_provider():
    init_chat_state()
    return st.session_state.chat_provider


def generate_hero_response(query: str) -> str:
    """Generates a contextual hero response from Athena."""
    provider = get_chat_provider()
    builder = PromptBuilder()
    prompt_pkg = builder.build(query, None, "general")
    try:
        resp = provider.generate(prompt_pkg)
        return resp.generated_text
    except Exception as e:
        return f"An error occurred: {e}"


def build_context_for_prompt(
    query: str,
    active_workspace_id: str,
    selected_player_id: int | None,
    selected_team_id: int | None,
):
    """Builds the actual context object based on active UI state and query intent."""
    engine = ExplanationContextEngine()

    player_id_list = [selected_player_id] if selected_player_id else None
    classification = IntentClassifier.classify(
        query, active_workspace_id, player_id_list
    )

    if (
        classification.intent == ConversationIntent.PLAYER_ANALYSIS
        and selected_player_id
    ):
        career = get_player_career(selected_player_id)
        if career:
            contexts = [engine.get_player_context(p) for p in career]
            if len(contexts) == 1:
                return contexts[0], "player"
            return contexts, "player_multi"

    if classification.intent == ConversationIntent.TEAM_ANALYSIS and selected_team_id:
        t = get_collective_profile(selected_team_id)
        if t:
            return engine.get_team_context(t), "team"

    return None, classification.intent.value


def process_athena_turn(
    query: str,
    active_workspace_id: str,
    selected_player_id: int | None,
    selected_team_id: int | None,
):
    """Orchestrates an Ask Athena chat turn."""
    manager = get_chat_manager()
    provider = get_chat_provider()

    # Detect context shifts
    manager.detect_and_handle_context_change(
        selected_player_id, selected_team_id, active_workspace_id
    )

    # Build prompt and execute
    builder = PromptBuilder()
    context_obj, prompt_type = build_context_for_prompt(
        query, active_workspace_id, selected_player_id, selected_team_id
    )

    prompt_pkg = builder.build(query, context_obj, prompt_type)

    try:
        response = provider.generate(prompt_pkg)

        # Telemetry
        from backend.explanation.telemetry import ExplanationTelemetry

        usage = response.usage or {}
        tokens_completion = usage.get("completion_tokens", 0)
        tokens_prompt = usage.get("prompt_tokens", 0)

        telemetry = ExplanationTelemetry(
            provider=response.provider,
            model=response.model,
            prompt_version=prompt_pkg.prompt_version,
            context_size_bytes=len(prompt_pkg.serialized_context),
            latency_ms=0.0,  # Not currently tracked at provider level
            streaming_duration_ms=0.0,
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            status="success",
        )
        record_telemetry(telemetry)

        manager.add_assistant_message(response.generated_text)
        return response.generated_text

    except Exception as e:
        error_msg = f"Athena encountered an error: {e}"
        manager.add_assistant_message(error_msg)
        return error_msg
