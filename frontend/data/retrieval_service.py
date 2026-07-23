"""
frontend/data/retrieval_service.py — Retrieval-enabled Ask Athena service.

Provides a retrieval-enhanced alternative to process_athena_turn that
adapts existing UI state into a StructuredIntent and runs the full
retrieval pipeline.

This is an additive code path — the original process_athena_turn
remains untouched as the baseline.
"""

from __future__ import annotations

import logging

from backend.explanation.conversation import ConversationManager
from backend.explanation.intent import ConversationIntent
from backend.explanation.providers.factory import get_provider
from backend.retrieval.bridge import RetrievalPromptBridge
from backend.retrieval.coverage import CoverageValidationError
from shared.config.settings import settings
from shared.schemas.retrieval import (
    IntentType,
    StructuredIntent,
)

logger = logging.getLogger(__name__)

# ─── Intent adapter ───────────────────────────────────────────────────────────

_INTENT_MAP: dict[ConversationIntent, IntentType] = {
    ConversationIntent.PLAYER_ANALYSIS: IntentType.PLAYER_ANALYSIS,
    ConversationIntent.TEAM_ANALYSIS: IntentType.TEAM_ANALYSIS,
    ConversationIntent.COMPARE_PLAYERS: IntentType.COMPARE_PLAYERS,
    ConversationIntent.RECRUITMENT: IntentType.RECRUITMENT,
    ConversationIntent.COUNTERFACTUAL: IntentType.COUNTERFACTUAL,
    ConversationIntent.GENERAL: IntentType.GENERAL,
    ConversationIntent.UNKNOWN: IntentType.GENERAL,
}


def _adapt_intent(
    query: str,
    active_workspace_id: str,
    selected_player_id: int | None,
    selected_team_id: int | None,
) -> StructuredIntent:
    """Adapt existing UI state + query into a StructuredIntent.

    Uses the existing IntentClassifier to determine intent type,
    then maps entities from UI selection state.
    """
    from backend.explanation.intent import IntentClassifier

    classification = IntentClassifier.classify(
        query, active_workspace_id,
        [selected_player_id] if selected_player_id else None,
    )

    # Map the existing ConversationIntent to our IntentType
    primary_type = _INTENT_MAP.get(
        classification.intent,
        IntentType.GENERAL,
    )

    entities: dict[str, str] = {}
    if selected_player_id is not None:
        entities["focus_player"] = str(selected_player_id)
    if selected_team_id is not None:
        entities["team"] = str(selected_team_id)

    return StructuredIntent(
        primary_type=primary_type,
        entities=entities,
        raw_text=query,
    )


# ─── Retrieval service ────────────────────────────────────────────────────────


class RetrievalAthenaService:
    """Retrieval-enhanced Ask Athena service.

    Wraps the retrieval pipeline so it can be called from the existing
    Streamlit UI with the same interface as process_athena_turn.
    """

    def __init__(self):
        self.bridge = RetrievalPromptBridge()
        self.manager = ConversationManager()
        self.provider = get_provider(settings.ATHENA_PROVIDER)

    def process_turn(
        self,
        query: str,
        active_workspace_id: str,
        selected_player_id: int | None,
        selected_team_id: int | None,
    ) -> str:
        """Process an Ask Athena turn with retrieval-enhanced evidence.

        Returns the generated response text, or an error message if
        retrieval fails or coverage is insufficient.
        """
        self.manager.add_user_message(query)

        intent = _adapt_intent(
            query, active_workspace_id,
            selected_player_id, selected_team_id,
        )

        try:
            prompt_pkg = self.bridge.build_prompt(query, intent)
        except CoverageValidationError as e:
            msg = (
                f"Athena does not have sufficient evidence to answer this "
                f"question. Missing evidence types: {e.missing}. "
                f"Please try a more specific question about a known player or team."
            )
            self.manager.add_assistant_message(msg)
            return msg

        try:
            response = self.provider.generate(prompt_pkg)

            # Build retrieval trace for Evidence Inspector
            trace_meta = dict(prompt_pkg.metadata) if prompt_pkg.metadata else {}
            trace_meta["response_model"] = response.model
            trace_meta["response_provider"] = response.provider

            self.manager.add_assistant_message(response.generated_text, metadata=trace_meta)
            return response.generated_text

        except Exception as e:
            error_msg = f"Athena encountered an error: {e}"
            self.manager.add_assistant_message(error_msg)
            return error_msg

    def clear_conversation(self) -> None:
        """Clear conversation history."""
        self.manager.clear()
