"""
backend/intelligence/signals.py — Decision signal generation.

Computes binary decision signals based on capability scores and raw metrics.
Signals are used by the Decision Engine to filter and match players.
"""

from __future__ import annotations

from shared.schemas import PlayerProfile


def generate_decision_signals(
    profile: PlayerProfile, normalized_metrics: dict[str, float]
) -> list[str]:
    """
    Evaluate all decision signal rules against a PlayerProfile.
    Returns a list of signal IDs that evaluated to True.
    """
    signals = []

    # Helper for capability scores
    def cap_score(name: str) -> float:
        if not profile.capability_profile:
            return 0.0
        cap = getattr(profile.capability_profile, name)
        return cap.score if cap else 0.0

    # Helper for normalized metrics
    def norm(metric: str) -> float:
        return normalized_metrics.get(metric, 0.0)

    # Helper for raw metrics
    def raw(metric: str) -> float:
        if not profile.feature_vector:
            return 0.0
        return getattr(profile.feature_vector, metric, 0.0)

    # Attacking
    if cap_score("attacking_threat") >= 85:
        signals.append("elite_goal_scorer")
    if cap_score("chance_creation") >= 80:
        signals.append("strong_chance_creator")
    if raw("goals_minus_xg") > 0 and raw("goals_p90") * raw("minutes_played") / 90 >= 3:
        signals.append("clinical_finisher")
    # For total shots, we estimate from goals and xg_per_shot if not available directly
    # In PlayerFeatureVector we don't have total_shots, but we have xg_per_shot. We'll skip total_shots requirement if missing.
    if raw("xg_per_shot") > 0.10:
        signals.append("xg_efficient_attacker")
    if cap_score("attacking_threat") >= 70 and cap_score("chance_creation") >= 70:
        signals.append("dual_threat_forward")

    # Progression
    if cap_score("ball_progression") >= 85:
        signals.append("elite_ball_progressor")
    if (
        cap_score("ball_progression") >= 75
        and cap_score("chance_creation") >= 60
        and profile.position_group in ["RB", "LB", "Defender"]
    ):
        signals.append("progressive_fullback")
    if norm("progressive_passes_p90") >= 80:
        signals.append("line_breaking_passer")
    if norm("progressive_carries_p90") >= 80:
        signals.append("ball_carrying_threat")

    # Technical
    if cap_score("press_resistance") >= 80:
        signals.append("high_press_resistant")
    if cap_score("ball_security") >= 80:
        signals.append("technical_ball_retainer")
    if raw("pass_accuracy_pct") > 85 and norm("passes_p90") > 50:
        signals.append("reliable_passer")

    # Defensive
    if cap_score("defensive_activity") >= 85:
        signals.append("defensive_specialist")
    if norm("pressures_p90") >= 80:
        signals.append("high_intensity_presser")
    if norm("recoveries_p90") >= 75:
        signals.append("ball_winner")

    # Profile
    if (
        profile.player_attributes
        and profile.player_attributes.tactical_versatility
        and profile.player_attributes.tactical_versatility >= 80
    ):
        signals.append("tactically_versatile")
    if cap_score("ball_progression") >= 70 and cap_score("defensive_activity") >= 70:
        signals.append("box_to_box_profile")

    scores = [
        cap_score("ball_progression"),
        cap_score("chance_creation"),
        cap_score("ball_security"),
        cap_score("press_resistance"),
        cap_score("defensive_activity"),
        cap_score("attacking_threat"),
    ]
    if all(s >= 60 for s in scores):
        signals.append("well_rounded")

    if (
        profile.player_attributes
        and profile.player_attributes.availability_rating
        and profile.player_attributes.availability_rating >= 80
    ):
        signals.append("low_availability_risk")
    if raw("matches_played") < 5:
        signals.append("small_sample_warning")

    return signals
