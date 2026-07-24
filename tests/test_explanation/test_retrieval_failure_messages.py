"""Tests for user-facing retrieval failure responses."""

from backend.explanation.conversation import ConversationManager
from backend.retrieval.bridge import CoverageValidationError
from frontend.data import retrieval_service
from frontend.data.retrieval_service import (
    RetrievalAthenaService,
    _build_failure_message,
)
from shared.schemas.retrieval import IntentType, StructuredIntent


def test_failure_message_explains_resolved_entities_and_safe_boundary():
    message = _build_failure_message(
        IntentType.PLAYER_ANALYSIS.value,
        {"players": [{"name": "Lionel Messi"}], "teams": []},
    )

    assert "player analysis" in message
    assert "Player: Lionel Messi" in message
    assert "won't fill the gaps with guesses" in message
    assert "Compare two players" in message
    assert "CoverageValidationError" not in message
    assert "Missing capability" not in message


def test_failure_message_handles_unresolved_entities_without_internal_terms():
    message = _build_failure_message(IntentType.GENERAL.value)

    assert "couldn't confidently match" in message
    assert "available data" in message
    assert "Retrieval failed" not in message


def test_coverage_failure_returns_the_user_safe_explanation(monkeypatch):
    class CoverageFailingBridge:
        def build_prompt(self, user_query, intent):
            raise CoverageValidationError("internal detail", ["key_difference"])

    intent = StructuredIntent(
        primary_type=IntentType.PLAYER_ANALYSIS,
        entities={"focus_player": "1"},
        raw_text="Analyze Lionel Messi",
    )
    monkeypatch.setattr(
        retrieval_service,
        "_adapt_intent",
        lambda *args: (intent, {"players": [{"name": "Lionel Messi"}], "teams": []}),
    )
    service = RetrievalAthenaService.__new__(RetrievalAthenaService)
    service.bridge = CoverageFailingBridge()
    service.manager = ConversationManager()

    message = service.process_turn("Analyze Lionel Messi", "workspace", None, None)

    assert "Lionel Messi" in message
    assert "won't fill the gaps with guesses" in message
    assert "CoverageValidationError" not in message
    assert "key_difference" not in message
