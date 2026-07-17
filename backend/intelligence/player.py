"""
backend/intelligence/player.py — Player Profile Generation.

Transforms normalized metrics and feature vectors into complete PlayerProfiles.
"""

from __future__ import annotations

from backend.intelligence.capabilities import (
    compute_physical_availability,
    compute_tactical_versatility,
    compute_weighted_capability,
)
from backend.intelligence.normalization import calculate_confidence
from shared.schemas import (
    CapabilityProfile,
    CapabilityScore,
    PlayerAttributes,
    PlayerFeatureVector,
    PlayerProfile,
)


def determine_role(
    capabilities: dict[str, CapabilityScore], position: str
) -> tuple[str, str]:
    """
    Evaluate the priority-ordered rule classifier to assign a role label.
    Returns (label, description).
    """

    # Helper to get score safely
    def score(cap_name: str) -> float:
        return capabilities[cap_name].score if cap_name in capabilities else 0.0

    # Priorities from FIE 6.5
    if score("attacking_threat") >= 85:
        return "Elite Goal Scorer", "Top 15% of position peers for direct goal threat"
    if score("chance_creation") >= 80 and score("ball_progression") >= 65:
        return (
            "Creative Playmaker",
            "High chance creation combined with progressive passing",
        )
    if score("ball_security") >= 80 and score("ball_progression") >= 75:
        return (
            "Deep-Lying Playmaker",
            "Excellent ball security with strong progressive passing",
        )
    if score("ball_progression") >= 70 and score("defensive_activity") >= 70:
        return (
            "Box-to-Box Midfielder",
            "Contributes strongly in both progression and defensive phases",
        )
    if (
        score("ball_progression") >= 75
        and score("chance_creation") >= 65
        and position in {"RB", "LB", "RWB", "LWB"}
    ):
        return (
            "Progressive Fullback",
            "Attacking fullback who drives forward and creates",
        )
    if score("defensive_activity") >= 85 and score("ball_security") >= 70:
        return (
            "Defensive Specialist",
            "Elite defensive contribution with secure possession",
        )
    if score("press_resistance") >= 85 and score("ball_security") >= 75:
        return "Press-Resistant Anchor", "Maintains control when pressed aggressively"
    if score("defensive_activity") >= 80 and score("tactical_versatility") >= 65:
        return "High-Energy Presser", "Relentless defensively and tactically versatile"
    if score("tactical_versatility") >= 85:
        return "Versatile Asset", "Effective across multiple roles and systems"

    # All-Round Contributor
    scores = [c.score for c in capabilities.values()]
    if all(s >= 40 for s in scores) and sum(1 for s in scores if s >= 60) >= 4:
        return (
            "All-Round Contributor",
            "Well-rounded profile with no material weaknesses",
        )

    # Developing Profile / Default
    return (
        "Developing Profile",
        "Developing statistical profile (often due to sample size)",
    )


def build_capability_profile(
    vector: PlayerFeatureVector,
    normalized_metrics: dict[str, float],
    competition_matches: int = 38,
) -> CapabilityProfile:
    """Build the 8-axis capability profile from normalized metrics."""
    confidence_val = calculate_confidence(vector.matches_played)

    from shared.config.capabilities import CORE_CAPABILITIES

    # Standard capabilities
    standard_caps = CORE_CAPABILITIES[:6]


    cap_scores: dict[str, CapabilityScore] = {}
    for cap in standard_caps:
        cap_scores[cap] = compute_weighted_capability(
            capability=cap,
            normalized_metrics=normalized_metrics,
            raw_vector=vector,
            position_group=vector.position_group,
            confidence=confidence_val,
        )

    # Remove physical_availability from CapabilityProfile
    # It will be calculated in build_player_profile for PlayerAttributes.

    # Tactical Versatility
    is_low_sample = vector.matches_played < 8
    raw_scores = {name: score.score for name, score in cap_scores.items()}
    cap_scores["tactical_versatility"] = compute_tactical_versatility(
        positions_played_count=vector.positions_played_count,
        capability_scores=raw_scores,
        confidence=confidence_val,
        is_low_sample=is_low_sample,
    )

    return CapabilityProfile(
        player_id=vector.player_id,
        player_name=vector.player_name,
        season=vector.season,
        competition=vector.competition,
        position_group=vector.position_group,
        minutes_played=vector.minutes_played,
        ball_progression=cap_scores["ball_progression"],
        chance_creation=cap_scores["chance_creation"],
        ball_security=cap_scores["ball_security"],
        press_resistance=cap_scores["press_resistance"],
        defensive_activity=cap_scores["defensive_activity"],
        attacking_threat=cap_scores["attacking_threat"],
        overall_rating=0.0 # Will be computed in engine after archetype assignment
    )

def compute_overall_rating(scores: dict, role_family: str) -> float:
    from backend.intelligence.roles import get_role_importance_vector
    
    pos_weights = get_role_importance_vector(role_family)

    total_score = 0.0
    total_weight = 0.0

    for cap_name, weight in pos_weights.items():
        if cap_name in scores and scores[cap_name] is not None:
            total_score += scores[cap_name].score * weight
            total_weight += weight

    if total_weight == 0:
        return 0.0
    return round(total_score / total_weight, 1)


def build_player_profile(
    vector: PlayerFeatureVector,
    normalized_metrics: dict[str, float],
    competition_matches: int = 38,
) -> PlayerProfile:
    """Construct a full PlayerProfile including capabilities, role, and context."""
    cap_profile = build_capability_profile(
        vector, normalized_metrics, competition_matches
    )

    # Extract scores into dict for easier role lookup
    cap_dict = {
        "ball_progression": cap_profile.ball_progression,
        "chance_creation": cap_profile.chance_creation,
        "ball_security": cap_profile.ball_security,
        "press_resistance": cap_profile.press_resistance,
        "defensive_activity": cap_profile.defensive_activity,
        "attacking_threat": cap_profile.attacking_threat,
    }
    # For role assignment we pass the raw dict (which has type dict[str, CapabilityScore])
    # However we need a dictionary of CapabilityScore
    typed_cap_dict = {k: v for k, v in cap_dict.items() if v is not None}

    # Delegate to Archetype Engine (deterministic percentile based)
    # For now, fallback to determine_role until archetype engine is fully written
    role_label, role_desc = determine_role(typed_cap_dict, vector.position_group)

    # Compute Tactical Versatility for attributes
    confidence_val = calculate_confidence(vector.matches_played)
    is_low_sample = vector.matches_played < 8
    raw_scores = {name: score.score for name, score in typed_cap_dict.items()}
    versatility_score = compute_tactical_versatility(
        positions_played_count=vector.positions_played_count,
        capability_scores=raw_scores,
        confidence=confidence_val,
        is_low_sample=is_low_sample,
    ).score

    matches_played_pct = normalized_metrics.get("matches_played", 50.0)
    coverage_rate = (
        vector.matches_played / float(competition_matches)
        if competition_matches > 0
        else 0.0
    )
    availability = compute_physical_availability(
        matches_played_percentile=matches_played_pct,
        matches_played_raw=vector.matches_played,
        coverage_rate=coverage_rate,
        confidence=confidence_val,
    ).score

    attributes = PlayerAttributes(
        tactical_versatility=versatility_score,
        minutes_reliability="High" if vector.matches_played >= 25 else "Medium" if vector.matches_played >= 15 else "Low",
        availability_rating=availability,
        positional_history=[vector.position_group], # Simplified for now
        seasons_indexed=1,
        competitions_indexed=1,
    )

    # Use age_years=0.0 as it's not in PlayerFeatureVector directly in the spec
    # unless we pass it separately. We will default to 0.0 for now.
    return PlayerProfile(
        player_id=vector.player_id,
        player_name=vector.player_name,
        position_group=vector.position_group,
        team_name=vector.team_name,
        competition=vector.competition,
        season=vector.season,
        profile_type=vector.profile_type,
        birth_date=vector.birth_date,
        minutes_played=vector.minutes_played,
        capability_profile=cap_profile,
        feature_vector=vector,
        player_attributes=attributes,
        archetype_profile=None,
        rating_presentation=None,
        similar_players=[],
    )
