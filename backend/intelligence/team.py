"""
backend/intelligence/team.py — Team Intelligence and Style Classification.

Aggregates PlayerProfiles to create a TeamProfile, assigning tactical identities
based on the aggregate capabilities.
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.intelligence.normalization import standard_deviation
from shared.schemas import PlayerProfile, TeamProfile


def aggregate_capabilities(players: Sequence[PlayerProfile]) -> dict[str, float]:
    """
    Compute appearances-weighted mean for all 8 capabilities.
    Only considers players with >= 5 appearances.
    """
    eligible = [
        p for p in players if p.feature_vector and p.feature_vector.matches_played >= 5
    ]
    if not eligible:
        # Fallback to all if no one meets threshold (e.g. early season)
        eligible = [p for p in players if p.feature_vector]

    if not eligible:
        return {}

    total_matches = sum(
        p.feature_vector.matches_played for p in eligible if p.feature_vector
    )
    if total_matches == 0:
        return {}

    from shared.config.capabilities import CORE_CAPABILITIES

    capabilities = CORE_CAPABILITIES


    agg_scores = {}
    for cap in capabilities:
        weighted_sum = 0.0
        for p in eligible:
            if not p.capability_profile or not p.feature_vector:
                continue
            cap_obj = getattr(p.capability_profile, cap)
            score = cap_obj.score if cap_obj else 0.0
            weighted_sum += score * p.feature_vector.matches_played
        agg_scores[cap] = weighted_sum / total_matches

    return agg_scores


def compute_squad_depth(players: Sequence[PlayerProfile]) -> float:
    """
    Compute squad depth score.
    squad_depth = 100 * (1 - mean(std_dev_per_capability) / 50)
    """
    eligible = [
        p for p in players if p.feature_vector and p.feature_vector.matches_played >= 5
    ]
    if not eligible:
        eligible = [p for p in players if p.feature_vector]
    if not eligible:
        return 0.0

    from shared.config.capabilities import CORE_CAPABILITIES
    capabilities = CORE_CAPABILITIES


    std_devs = []
    for cap in capabilities:
        scores = []
        for p in eligible:
            if p.capability_profile:
                cap_obj = getattr(p.capability_profile, cap)
                if cap_obj:
                    scores.append(cap_obj.score)
        if scores:
            std_devs.append(standard_deviation(scores))

    if not std_devs:
        return 0.0

    mean_std_dev = sum(std_devs) / len(std_devs)
    depth = 100.0 * (1.0 - (mean_std_dev / 50.0))
    return max(0.0, min(100.0, depth))


def determine_playing_style(agg: dict[str, float]) -> str:
    """Determine playing style label based on aggregate capabilities."""

    def score(cap: str) -> float:
        return agg.get(cap, 0.0)

    if score("ball_security") >= 70 and score("ball_progression") >= 70:
        return "Possession-Dominant"
    if score("defensive_activity") >= 75 and score("press_resistance") >= 65:
        return "High Press"
    # avg_pass_length > competition median requires context, simplified here
    if score("ball_progression") >= 70 and score("chance_creation") >= 65:
        return "Direct and Progressive"
    if (
        score("attacking_threat") >= 70
        and score("defensive_activity") >= 65
        and score("ball_security") <= 55
    ):
        return "Counter-Attacking"
    if score("defensive_activity") >= 80 and score("attacking_threat") <= 50:
        return "Defensive and Resilient"

    return "Balanced"


def build_team_profile(
    team_id: int,
    team_name: str,
    competition: str,
    season: str,
    players: Sequence[PlayerProfile],
) -> TeamProfile:
    """Aggregate a squad of PlayerProfiles into a TeamProfile."""
    agg = aggregate_capabilities(players)
    style = determine_playing_style(agg)

    # Deterministic Strengths & Weaknesses
    # Sort capabilities by score
    sorted_caps = sorted([(k, v) for k, v in agg.items() if v > 0], key=lambda x: x[1], reverse=True)

    strengths = []
    weaknesses = []

    if sorted_caps:
        # Top 2 are strengths if they are above 60
        for cap, score in sorted_caps[:2]:
            if score >= 60.0:
                strengths.append(cap.replace("_", " ").title())

        # Bottom 2 are weaknesses if they are below 50
        for cap, score in sorted_caps[-2:]:
            if score < 50.0:
                weaknesses.append(cap.replace("_", " ").title())

    return TeamProfile(
        team_id=team_id,
        team_name=team_name,
        competition=competition,
        season=season,
        squad_size=len(players),
        avg_ball_progression=agg.get("ball_progression", 0.0),
        avg_chance_creation=agg.get("chance_creation", 0.0),
        avg_ball_security=agg.get("ball_security", 0.0),
        avg_press_resistance=agg.get("press_resistance", 0.0),
        avg_defensive_activity=agg.get("defensive_activity", 0.0),
        avg_attacking_threat=agg.get("attacking_threat", 0.0),
        avg_physical_availability=agg.get("physical_availability", 0.0),
        avg_tactical_versatility=agg.get("tactical_versatility", 0.0),
        style_label=style,
        strengths=strengths,
        weaknesses=weaknesses
    )
