"""
backend/recommendation/recruitment.py — Recruitment Ranking Engine.

Executes search queries, ranks players based on fit criteria, and provides
replacement recommendations.
"""

from __future__ import annotations

from typing import Sequence
from shared.schemas import PlayerProfile, RecruitmentCriteria, RecruitmentCandidate
from backend.recommendation.matching import evaluate_tactical_fit
from backend.recommendation.tradeoffs import generate_tradeoffs
from backend.intelligence.normalization import euclidean_distance


def _get_capability_score(player: PlayerProfile, capability: str) -> float:
    if not player.capability_profile:
        return 0.0
    cap = getattr(player.capability_profile, capability)
    return cap.score if cap else 0.0


def rank_candidates(pool: Sequence[PlayerProfile], criteria: RecruitmentCriteria) -> list[RecruitmentCandidate]:
    """
    Filter and rank a cohort of players based on specified RecruitmentCriteria.
    """
    candidates = []

    for player in pool:
        if criteria.excluded_player_ids and player.player_id in criteria.excluded_player_ids:
            continue
            
        if criteria.position and player.position_group != criteria.position:
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
        tactical_fit = 0.0
        if criteria.tactical_style:
            tactical_fit = evaluate_tactical_fit(player, criteria.tactical_style)
            # Blend base score and tactical fit
            fit_score = (base_score * 0.70) + (tactical_fit * 0.30)
        else:
            fit_score = base_score

        # 3. Generate Trade-offs and Context
        strengths, trade_offs, explanation_context = generate_tradeoffs(
            player=player, 
            criteria=criteria, 
            tactical_fit_score=tactical_fit
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
            decision_signals=player.decision_signals,
            strengths=strengths,
            trade_offs=trade_offs,
            confidence=confidence,
            explanation_context=explanation_context
        )
        candidates.append(candidate)

    # Sort descending by fit_score
    candidates.sort(key=lambda c: c.fit_score, reverse=True)
    
    # Assign ranks
    for i, c in enumerate(candidates):
        c.rank = i + 1

    return candidates[:criteria.max_results]


def recommend_replacement(
    target: PlayerProfile, 
    pool: Sequence[PlayerProfile],
    tactical_style: str | None = None,
    max_results: int = 5
) -> list[RecruitmentCandidate]:
    """
    Recommend a replacement combining Similarity, Tactical Fit, and Availability.
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
        
        # 1. Similarity (Euclidean Distance normalized to 0-100)
        max_dist = 245.0  # roughly sqrt(6 * 100^2)
        dist = euclidean_distance(target_vector, player_vector)
        similarity_score = 100.0 * (1.0 - (dist / max_dist))
        similarity_score = max(0.0, min(100.0, similarity_score))
        
        # 2. Tactical Fit (if specified, otherwise default to similarity)
        if tactical_style:
            tactical_score = evaluate_tactical_fit(player, tactical_style)
        else:
            tactical_score = similarity_score
            
        # 3. Physical Availability (important for replacements)
        availability = _get_capability_score(player, "physical_availability")
        
        # Combine: 50% Similarity, 30% Tactical, 20% Availability
        fit_score = (similarity_score * 0.50) + (tactical_score * 0.30) + (availability * 0.20)
        
        # Build explanation context
        explanation_context = {
            "similarity_to_target": similarity_score,
            "tactical_fit": tactical_score,
            "availability": availability
        }
        
        strengths = []
        trade_offs = []
        if similarity_score >= 85:
            strengths.append(f"Statistically very similar to {target.player_name}")
        elif similarity_score < 70:
            trade_offs.append(f"Stylistically divergent from {target.player_name}")
            
        if availability >= 80:
            strengths.append("High physical availability and reliability")
        elif availability < 60:
            trade_offs.append("Availability concerns")

        confidence = "high" if player.minutes_played > 1800 else "medium"

        candidate = RecruitmentCandidate(
            player=player,
            fit_score=fit_score,
            decision_signals=player.decision_signals,
            strengths=strengths,
            trade_offs=trade_offs,
            confidence=confidence,
            explanation_context=explanation_context
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: c.fit_score, reverse=True)
    
    for i, c in enumerate(candidates):
        c.rank = i + 1

    return candidates[:max_results]
