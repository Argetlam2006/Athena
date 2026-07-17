"""
backend/explanation/intent.py — Deterministic Intent Routing.

Replaces heuristic string parsing with an explicit Intent classifier
that dictates what data context to retrieve.
"""

from dataclasses import dataclass
from enum import Enum


class ConversationIntent(str, Enum):
    PLAYER_ANALYSIS = "player_analysis"
    TEAM_ANALYSIS = "team_analysis"
    COMPARE_PLAYERS = "compare_players"
    RECRUITMENT = "recruitment"
    COUNTERFACTUAL = "counterfactual"
    GENERAL = "general"
    UNKNOWN = "unknown"


@dataclass
class IntentClassification:
    intent: ConversationIntent
    required_entities: list[str]
    required_context: str | None


class IntentClassifier:
    """
    Deterministically maps user queries and UI state to an exact analytical intent.
    """

    @staticmethod
    def classify(
        query: str, active_workspace: str, selected_ids: list[int] = None
    ) -> IntentClassification:
        q_lower = query.lower()

        # Explicit Keyword Overrides (Strongest Signal)
        if "compare" in q_lower or "vs" in q_lower:
            return IntentClassification(
                ConversationIntent.COMPARE_PLAYERS, [], "Comparison"
            )

        if (
            "recruit" in q_lower
            or "find similar" in q_lower
            or "sign" in q_lower
            or "scout" in q_lower
        ):
            return IntentClassification(
                ConversationIntent.RECRUITMENT, [], "Recruitment"
            )

        if (
            "what if" in q_lower
            or "remove" in q_lower
            or "add" in q_lower
            or "without" in q_lower
        ):
            return IntentClassification(
                ConversationIntent.COUNTERFACTUAL, [], "Counterfactual"
            )

        # UI State Driven
        if active_workspace == "player_intelligence":
            return IntentClassification(
                ConversationIntent.PLAYER_ANALYSIS, [], "Player"
            )

        if active_workspace == "team_intelligence":
            return IntentClassification(ConversationIntent.TEAM_ANALYSIS, [], "Team")

        if active_workspace == "recruitment":
            return IntentClassification(
                ConversationIntent.RECRUITMENT, [], "Recruitment"
            )

        # Fallback keyword checks
        if "team" in q_lower or "squad" in q_lower or "tactic" in q_lower:
            return IntentClassification(ConversationIntent.TEAM_ANALYSIS, [], "Team")

        if "player" in q_lower or "profile" in q_lower:
            return IntentClassification(
                ConversationIntent.PLAYER_ANALYSIS, [], "Player"
            )

        return IntentClassification(ConversationIntent.GENERAL, [], "General")
