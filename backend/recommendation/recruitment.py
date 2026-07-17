"""
backend/recommendation/recruitment.py - Recruitment Ranking Engine.

Executes search queries, ranks players based on fit criteria, and provides
replacement recommendations.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.intelligence.normalization import euclidean_distance
from backend.recommendation.matching import evaluate_tactical_fit
from backend.recommendation.tradeoffs import generate_tradeoffs
from shared.constants import BROAD_POSITION_MAP
from shared.schemas import PlayerProfile, RecruitmentCandidate, RecruitmentCriteria


def _get_capability_score(player: PlayerProfile, capability: str) -> float:
    if not player.capability_profile:
        return 0.0
    cap = getattr(player.capability_profile, capability)
    return cap.score if cap else 0.0


def rank_candidates(
    pool: Sequence[PlayerProfile], criteria: RecruitmentCriteria
) -> list[RecruitmentCandidate]:
    """
    Filter and rank a cohort of players based on specified RecruitmentCriteria.
    """
    candidates = []

    for player in pool:
        if (
            criteria.excluded_player_ids
            and player.player_id in criteria.excluded_player_ids
        ):
            continue

        if criteria.position:
            if criteria.position in BROAD_POSITION_MAP:
                if player.position_group not in BROAD_POSITION_MAP[criteria.position]:
                    continue
            elif player.position_group != criteria.position:
                continue

        if player.minutes_played < criteria.min_minutes:
            continue

        if not player.capability_profile:
            continue

        # 1. Base Criteria Score (Weighted sum of required/preferred capabilities)
        base_score = 0.0
        total_weight = 0.0

        for cap, weight in criteria.required_capabilities.items():
            base_score += _get_capability_score(player, cap) * weight
            total_weight += weight

        for cap, weight in criteria.preferred_capabilities.items():
            base_score += _get_capability_score(player, cap) * weight
            total_weight += weight

        if total_weight > 0:
            base_score = base_score / total_weight
        else:
            base_score = 50.0  # Fallback if no specific requirements

        # 2. Tactical Fit Adjustment
        tactical_fit = None
        if criteria.tactical_style:
            tactical_fit = evaluate_tactical_fit(player, criteria.tactical_style)
            # Blend base score and tactical fit
            fit_score = (base_score * 0.70) + (
                tactical_fit.overall_compatibility * 0.30
            )
        else:
            fit_score = base_score

        # 3. Generate Trade-offs and Context
        strengths, trade_offs, explanation_context = generate_tradeoffs(
            player=player,
            criteria=criteria,
            tactical_fit_score=tactical_fit.overall_compatibility
            if tactical_fit
            else 0.0,
        )

        # Determine confidence
        confidence = "medium"
        if player.minutes_played > 1800:
            confidence = "high"
        elif player.minutes_played < 900:
            confidence = "low"

        candidate = RecruitmentCandidate(
            player=player,
            fit_score=fit_score,
            restoration={},
            trade_offs_positive=strengths,
            trade_offs_negative=trade_offs,
            overall_team_impact="Aligns with requested recruitment criteria.",
            confidence=confidence,
            explanation_context=explanation_context,
            system_compatibility=tactical_fit,
            player_attributes=player.player_attributes,
        )
        candidates.append(candidate)

    # Sort descending by fit_score
    candidates.sort(key=lambda c: c.fit_score, reverse=True)

    # Assign ranks
    for i, c in enumerate(candidates):
        c.rank = i + 1

    return candidates[: criteria.max_results]


def recommend_replacement(
    target: PlayerProfile,
    pool: Sequence[PlayerProfile],
    tactical_style: str | None = None,
    max_results: int = 5,
) -> list[RecruitmentCandidate]:
    """
    Recommend a replacement using Capability Restoration rather than simple similarity.
    """
    candidates = []

    if not target.capability_profile:
        return []

    target_vector = [
        _get_capability_score(target, "ball_progression"),
        _get_capability_score(target, "chance_creation"),
        _get_capability_score(target, "ball_security"),
        _get_capability_score(target, "press_resistance"),
        _get_capability_score(target, "defensive_activity"),
        _get_capability_score(target, "attacking_threat"),
    ]

    cap_names = [
        "Ball Progression",
        "Chance Creation",
        "Ball Security",
        "Press Resistance",
        "Defensive Activity",
        "Attacking Threat",
    ]

    for player in pool:
        if player.player_id == target.player_id:
            continue
        if player.position_group != target.position_group:
            continue
        if not player.capability_profile:
            continue

        player_vector = [
            _get_capability_score(player, "ball_progression"),
            _get_capability_score(player, "chance_creation"),
            _get_capability_score(player, "ball_security"),
            _get_capability_score(player, "press_resistance"),
            _get_capability_score(player, "defensive_activity"),
            _get_capability_score(player, "attacking_threat"),
        ]

        # 1. Base Fit (Euclidean Distance normalized to 0-100)
        max_dist = 245.0
        dist = euclidean_distance(target_vector, player_vector)
        fit_score = max(0.0, min(100.0, 100.0 * (1.0 - (dist / max_dist))))

        # 2. Capability Restoration & Trade-offs
        restoration = {}
        trade_offs_positive = []
        trade_offs_negative = []

        for i, cap in enumerate(cap_names):
            t_val = target_vector[i]
            p_val = player_vector[i]

            if t_val > 0:
                pct = (p_val / t_val) * 100
                restoration[cap] = f"{round(pct)}%"

                # Trade-offs
                if pct > 110:
                    trade_offs_positive.append(f"Enhanced {cap}")
                elif pct < 85:
                    trade_offs_negative.append(f"Reduced {cap}")

        confidence = "high" if player.minutes_played > 1800 else "medium"

        candidate = RecruitmentCandidate(
            player=player,
            fit_score=fit_score,
            restoration=restoration,
            trade_offs_positive=trade_offs_positive,
            trade_offs_negative=trade_offs_negative,
            overall_team_impact=f"Restores majority profile with {len(trade_offs_positive)} enhancements and {len(trade_offs_negative)} regressions.",
            confidence=confidence,
            explanation_context={},
            system_compatibility=None,  # Computed separately if needed
            player_attributes=player.player_attributes,
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: c.fit_score, reverse=True)

    for i, c in enumerate(candidates):
        c.rank = i + 1

    return candidates[:max_results]
