"""
backend/recommendation/engine.py — Decision Intelligence Engine Facade.

The primary entry point for all decision intelligence operations, consuming
outputs from the Football Intelligence Engine to produce actionable recommendations.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from backend.recommendation.comparison import compare_players
from backend.recommendation.matching import (
    evaluate_tactical_fit,
    get_tactical_fit_explanation,
)
from backend.recommendation.recruitment import rank_candidates, recommend_replacement
from shared.schemas import (
    CollectiveProfile,
    ComparisonResult,
    PlayerProfile,
    RecruitmentCandidate,
    RecruitmentCriteria,
)

logger = logging.getLogger(__name__)


class DecisionIntelligenceEngine:
    """
    Facade for the Decision Intelligence Layer.

    Transforms PlayerProfiles and CollectiveProfiles into explainable football decisions.
    Never computes capabilities directly; relies entirely on the upstream FIE.
    """

    def __init__(self):
        pass

    def compare_players(self, profiles: list[PlayerProfile]) -> ComparisonResult:
        """
        Compare two or more players quantitatively across all capabilities.

        Args:
            profiles: A list of PlayerProfile objects to compare.

        Returns:
            ComparisonResult containing structured insights and a summary.
        """
        if len(profiles) < 2:
            logger.warning("compare_players called with fewer than 2 players.")
        return compare_players(profiles)

    def rank_candidates(
        self, pool: Sequence[PlayerProfile], criteria: RecruitmentCriteria
    ) -> list[RecruitmentCandidate]:
        """
        Filter and rank a cohort of players based on specific RecruitmentCriteria.

        Args:
            pool: The universe of PlayerProfiles to evaluate.
            criteria: The required positional, tactical, and capability criteria.

        Returns:
            A sorted list of RecruitmentCandidate objects containing fit scores and explainability context.
        """
        return rank_candidates(pool, criteria)

    def recommend_replacement(
        self,
        target: PlayerProfile,
        pool: Sequence[PlayerProfile],
        tactical_style: str | None = None,
        max_results: int = 5,
    ) -> list[RecruitmentCandidate]:
        """
        Recommend the best replacements for a specific player.

        Args:
            target: The PlayerProfile being replaced.
            pool: The candidate pool.
            tactical_style: Optional tactical system to factor into the replacement.
            max_results: Number of recommendations to return.

        Returns:
            A sorted list of RecruitmentCandidate objects matching the target's profile.
        """
        return recommend_replacement(target, pool, tactical_style, max_results)

    def evaluate_team_fit(
        self, player: PlayerProfile, team: CollectiveProfile
    ) -> dict[str, str | float]:
        """
        Evaluate how well a player fits into a specific team's tactical style.

        Args:
            player: The player to evaluate.
            team: The target CollectiveProfile.

        Returns:
            Dictionary containing the fit score and a natural language explanation.
        """
        style = team.identity.primary_identity if team.identity else "Balanced"
        tactical_fit = evaluate_tactical_fit(player, style, team)
        fit_score = tactical_fit.overall_compatibility
        explanation = get_tactical_fit_explanation(player, style, fit_score)

        return {
            "player_name": player.player_name,
            "target_team": team.team_name,
            "target_style": style,
            "fit_score": fit_score,
            "explanation": explanation,
            "capability_alignment": tactical_fit.capability_alignment,
            "tactical_identity_preservation": tactical_fit.tactical_identity_preservation,
            "dependency_relief": tactical_fit.dependency_relief,
            "contextual_trade_offs": tactical_fit.contextual_trade_offs,
            "availability_impact": tactical_fit.availability_impact,
        }
