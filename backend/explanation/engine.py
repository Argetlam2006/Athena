"""
backend/explanation/engine.py — Explanation Context Engine Facade.

The public API for the Explanation Context layer. Converts internal intelligence
models into structured, verified evidence payloads for the LLM.
"""

import logging

from backend.explanation.builder import (
    build_comparison_context,
    build_player_context,
    build_recruitment_context,
    build_team_context,
)
from backend.explanation.context import (
    ComparisonExplanationContext,
    PlayerExplanationContext,
    RecruitmentExplanationContext,
    TeamExplanationContext,
)
from backend.explanation.validator import (
    validate_comparison_context,
    validate_player_context,
    validate_recruitment_context,
    validate_team_context,
)
from shared.schemas import (
    CollectiveProfile,
    ComparisonResult,
    PlayerProfile,
    RecruitmentCandidate,
    RecruitmentCriteria,
)

logger = logging.getLogger(__name__)


class ExplanationContextEngine:
    """
    Facade for the Context Engine.
    Builds and validates semantic evidence payloads.
    """

    def get_player_context(self, profile: PlayerProfile) -> PlayerExplanationContext:
        """
        Builds and validates an explanation context for a PlayerProfile.
        Raises ContextValidationError if incomplete.
        """
        context = build_player_context(profile)
        validate_player_context(context)
        return context

    def get_team_context(self, profile: CollectiveProfile) -> TeamExplanationContext:
        """
        Builds and validates an explanation context for a CollectiveProfile.
        Raises ContextValidationError if incomplete.
        """
        context = build_team_context(profile)
        validate_team_context(context)
        return context

    def get_recruitment_context(
        self, criteria: RecruitmentCriteria, candidates: list[RecruitmentCandidate]
    ) -> RecruitmentExplanationContext:
        """
        Builds and validates an explanation context for a recruitment recommendation.
        Raises ContextValidationError if incomplete.
        """
        context = build_recruitment_context(criteria, candidates)
        validate_recruitment_context(context)
        return context

    def get_comparison_context(
        self, result: ComparisonResult
    ) -> ComparisonExplanationContext:
        """
        Builds and validates an explanation context for a comparison result.
        Raises ContextValidationError if incomplete.
        """
        context = build_comparison_context(result)
        validate_comparison_context(context)
        return context
