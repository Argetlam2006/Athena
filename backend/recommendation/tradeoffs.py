"""
backend/recommendation/tradeoffs.py — Trade-off and Evidence Generator.

Generates structured evidence, identifying strengths and weaknesses based on
required criteria and capability profiles.
"""

from __future__ import annotations

from typing import Any

from shared.schemas import PlayerProfile, RecruitmentCriteria


def generate_tradeoffs(
    player: PlayerProfile,
    criteria: RecruitmentCriteria,
    tactical_fit_score: float = 0.0,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """
    Generate strengths, trade-offs (weaknesses), and context for explanation.
    """
    strengths = []
    trade_offs = []
    explanation_context: dict[str, Any] = {
        "tactical_fit_score": tactical_fit_score,
        "criteria_match": {},
        "signals": player.decision_signals,
        "archetype": player.display_archetype,
    }

    if not player.capability_profile:
        return strengths, trade_offs, explanation_context

    cap = player.capability_profile

    def score(name: str) -> float:
        val = getattr(cap, name)
        return val.score if val else 0.0

    # 1. Evaluate Required Capabilities
    for cap_name, _required_weight in criteria.required_capabilities.items():
        s = score(cap_name)
        explanation_context["criteria_match"][cap_name] = s

        display_name = cap_name.replace("_", " ").title()
        if s >= 80:
            strengths.append(f"Elite {display_name} ({s:.1f})")
        elif s >= 65:
            strengths.append(f"Strong {display_name} ({s:.1f})")
        elif s < 50:
            trade_offs.append(
                f"Below average {display_name} ({s:.1f}) relative to requirements"
            )

    # 2. Add strengths from Decision Signals if they align with preferred/required
    key_signals = {
        "elite_goal_scorer": "Elite goal threat",
        "strong_chance_creator": "Exceptional chance creation",
        "elite_ball_progressor": "Elite ball progression",
        "defensive_specialist": "Specialist defensive output",
        "tactically_versatile": "High tactical versatility",
        "high_press_resistant": "Excellent press resistance",
        "clinical_finisher": "Clinical finishing above xG",
    }
    for sig in player.decision_signals:
        if sig in key_signals and key_signals[sig] not in strengths:
            strengths.append(key_signals[sig])

    # 3. Add trade-offs from Decision Signals
    warning_signals = {
        "small_sample_warning": "Small sample size (low confidence)",
    }
    for sig in player.decision_signals:
        if sig in warning_signals and warning_signals[sig] not in trade_offs:
            trade_offs.append(warning_signals[sig])

    # Check physical availability explicitly if not required but low
    avail_score = (
        player.player_attributes.availability_rating
        if player.player_attributes
        and player.player_attributes.availability_rating is not None
        else 50.0
    )
    if avail_score < 50:
        trade_offs.append(f"Availability concerns (Score: {avail_score:.1f})")

    # Tactical fit
    if criteria.tactical_style:
        if tactical_fit_score >= 75:
            strengths.append(f"Strong fit for {criteria.tactical_style}")
        elif tactical_fit_score < 55:
            trade_offs.append(f"Poor stylistic fit for {criteria.tactical_style}")

    return strengths, trade_offs, explanation_context
