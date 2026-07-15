"""
backend/intelligence/capabilities.py — Capability score computation.

This module computes the 0-100 scores for each capability using normalized
percentile metrics and configured weights.
"""

from __future__ import annotations

from backend.intelligence.normalization import standard_deviation
from shared.config.capabilities import CAPABILITY_METRIC_WEIGHTS
from shared.schemas import CapabilityScore


def get_weights_for_position(capability: str, position_group: str) -> dict[str, float]:
    """Retrieve the metric weights for a given capability and position group."""
    weights = CAPABILITY_METRIC_WEIGHTS.get(capability, {})
    if not weights:
        return {}

    # If the weights are nested (e.g., "default", "Defender"), fetch appropriately
    if "default" in weights:
        # Some are based on specific groups (Forward/Defender), others on wide/central
        # For Chance Creation, the FIE mentions "wide" vs "central". We will map
        # Fullbacks and Wingers to "wide", others to "default" in the parent caller if needed,
        # but for safety we can just look up the key directly or fall back to default.
        return weights.get(position_group, weights["default"])

    return weights


def compute_weighted_capability(
    capability: str,
    normalized_metrics: dict[str, float],
    position_group: str,
    confidence: float,
) -> CapabilityScore:
    """
    Compute a standard weighted-sum capability score.

    Args:
        capability: The capability name (e.g. 'ball_progression').
        normalized_metrics: A dictionary of metric_name -> percentile (0-100).
        position_group: Used to look up specific weights if they differ by position.
        confidence: The confidence score for this capability (0-1).

    Returns:
        CapabilityScore object containing the final score and evidence.
    """
    weights = get_weights_for_position(capability, position_group)

    score = 0.0
    evidence: dict[str, float] = {}

    for metric, weight in weights.items():
        # Fallback to 0 if metric is missing (should not happen with valid data)
        val = normalized_metrics.get(metric, 0.0)
        score += val * weight
        evidence[metric] = val

    return CapabilityScore(
        capability=capability, score=score, confidence=confidence, evidence=evidence
    )


def compute_physical_availability(
    matches_played_percentile: float, coverage_rate: float, confidence: float
) -> CapabilityScore:
    """
    Compute Physical Availability.
    Formula: (coverage_rate * 100 * 0.60) + (matches_played_percentile * 0.40)
    """
    score = (coverage_rate * 100.0 * 0.60) + (matches_played_percentile * 0.40)

    return CapabilityScore(
        capability="physical_availability",
        score=min(100.0, score),
        confidence=confidence,
        evidence={
            "coverage_rate_pct": coverage_rate * 100.0,
            "matches_played_pct": matches_played_percentile,
        },
    )


def compute_tactical_versatility(
    positions_played_count: int,
    capability_scores: dict[str, float],
    confidence: float,
    is_low_sample: bool = False,
) -> CapabilityScore:
    """
    Compute Tactical Versatility.

    Dimensions:
    1. Positional Breadth (stepped scale based on positions with >= 3 apps)
       For our implementation, we use the raw count since the feature vector
       already provides it.
    2. Capability Profile Breadth = 100 * (1 - std_dev(all_scores) / 50)
    3. Phase Contribution Balance = min(att, def) / max(att, def) * 100
    """
    # 1. Positional Breadth
    if positions_played_count <= 1:
        pos_score = 0.0
    elif positions_played_count == 2:
        pos_score = 40.0
    elif positions_played_count == 3:
        pos_score = 70.0
    else:
        pos_score = 100.0

    # 2. Capability Breadth
    scores = list(capability_scores.values())
    if len(scores) < 7:
        cap_breadth = 50.0  # Safe fallback if not all capabilities are available yet
    else:
        std_dev = standard_deviation(scores)
        cap_breadth = 100.0 * (1.0 - (std_dev / 50.0))
        cap_breadth = max(0.0, min(100.0, cap_breadth))

    # 3. Phase Balance
    # attack = weighted_mean(Progression*0.35, Chance*0.35, Threat*0.30)
    prog = capability_scores.get("ball_progression", 0.0)
    chan = capability_scores.get("chance_creation", 0.0)
    thrt = capability_scores.get("attacking_threat", 0.0)
    attack_score = (prog * 0.35) + (chan * 0.35) + (thrt * 0.30)

    # def = weighted_mean(Defensive*0.60, Press*0.40)
    dfn = capability_scores.get("defensive_activity", 0.0)
    prs = capability_scores.get("press_resistance", 0.0)
    defense_score = (dfn * 0.60) + (prs * 0.40)

    max_phase = max(attack_score, defense_score)
    min_phase = min(attack_score, defense_score)
    phase_balance = (min_phase / max_phase * 100.0) if max_phase > 0 else 0.0

    # Apply weights (FIE 4.8)
    if is_low_sample:
        w_pos = 0.10
        w_cap = 0.55
        w_pha = 0.35
    else:
        w_pos = 0.25
        w_cap = 0.40
        w_pha = 0.35

    score = (pos_score * w_pos) + (cap_breadth * w_cap) + (phase_balance * w_pha)

    return CapabilityScore(
        capability="tactical_versatility",
        score=max(0.0, min(100.0, score)),
        confidence=confidence,
        evidence={
            "positional_breadth": pos_score,
            "capability_breadth": cap_breadth,
            "phase_balance": phase_balance,
        },
    )
