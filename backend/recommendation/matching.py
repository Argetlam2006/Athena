"""
backend/recommendation/matching.py — Tactical Fit Evaluation.

Evaluates how well a PlayerProfile fits a given CollectiveProfile or a tactical style,
decomposed into a highly structured SystemCompatibilityContext.
"""

from __future__ import annotations

from shared.schemas import CollectiveProfile, PlayerProfile, SystemCompatibilityContext


def evaluate_tactical_fit(
    player: PlayerProfile, target_style: str, team: CollectiveProfile | None = None
) -> SystemCompatibilityContext:
    """
    Evaluate the player's fit for a given tactical style and team context.
    Returns a decomposed SystemCompatibilityContext.
    """
    if not player.capability_profile:
        return SystemCompatibilityContext(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    cap = player.capability_profile

    def score(name: str) -> float:
        val = getattr(cap, name, None)
        return val.score if val else 0.0

    # 1. Capability Alignment (How well player matches the ideal style)
    alignment = 50.0
    if target_style == "Possession-Dominant":
        alignment = (score("ball_security") * 0.50) + (score("ball_progression") * 0.25) + (score("press_resistance") * 0.25)
    elif target_style == "High Press":
        alignment = (score("defensive_activity") * 0.60) + (score("press_resistance") * 0.40)
    elif target_style == "Direct and Progressive":
        alignment = (score("ball_progression") * 0.50) + (score("chance_creation") * 0.30) + (score("attacking_threat") * 0.20)
    elif target_style == "Counter-Attacking":
        alignment = (score("attacking_threat") * 0.50) + (score("ball_progression") * 0.30) + (score("defensive_activity") * 0.20)
    elif target_style == "Defensive and Resilient":
        alignment = (score("defensive_activity") * 0.60) + (score("ball_security") * 0.40)
    else:
        alignment = (score("ball_security") * 0.40) + (score("defensive_activity") * 0.40) + (score("ball_progression") * 0.20)

    # 2. Tactical Identity Preservation
    identity = 50.0
    relief = 50.0
    if team:
        # If team has weaknesses, does the player relieve them?
        weak_caps = [c for c, v in team.avg_capabilities.items() if v < 60.0] if hasattr(team, "avg_capabilities") else []
        if weak_caps:
            rel_sum = 0.0
            for w in weak_caps:
                key = w.lower().replace(" ", "_")
                rel_sum += score(key)
            relief = rel_sum / len(weak_caps)

    # 3. Contextual Trade-Offs (Using Versatility as proxy for adaptability)
    trade_offs = 50.0
    if player.player_attributes and player.player_attributes.tactical_versatility is not None:
        trade_offs = player.player_attributes.tactical_versatility

    # 4. Availability Impact
    availability = 50.0
    if player.player_attributes and player.player_attributes.availability_rating is not None:
        availability = player.player_attributes.availability_rating

    # Combine into Overall Compatibility
    # Weighting: Alignment (40%), Identity (20%), Relief (20%), Trade-offs (10%), Availability (10%)
    overall = (
        (alignment * 0.40) +
        (identity * 0.20) +
        (relief * 0.20) +
        (trade_offs * 0.10) +
        (availability * 0.10)
    )

    return SystemCompatibilityContext(
        capability_alignment=round(alignment, 1),
        tactical_identity_preservation=round(identity, 1),
        dependency_relief=round(relief, 1),
        contextual_trade_offs=round(trade_offs, 1),
        availability_impact=round(availability, 1),
        overall_compatibility=round(overall, 1)
    )


def get_tactical_fit_explanation(
    player: PlayerProfile, target_style: str, fit_score: float
) -> str:
    """Generate a brief explanation for the tactical fit score."""
    if fit_score >= 80:
        return f"Excellent fit for {target_style} system due to strong aligned capabilities."
    if fit_score >= 65:
        return f"Solid fit for {target_style} system."
    if fit_score >= 50:
        return f"Marginal fit for {target_style} system; some capability gaps exist."
    return f"Poor fit for {target_style} system; capabilities do not align."
