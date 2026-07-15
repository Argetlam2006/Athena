"""
backend/recommendation/matching.py — Tactical Fit Evaluation.

Evaluates how well a PlayerProfile fits a given TeamProfile or a tactical style.
"""

from __future__ import annotations

from shared.schemas import PlayerProfile, TeamProfile


def evaluate_tactical_fit(player: PlayerProfile, target_style: str) -> float:
    """
    Evaluate the player's fit for a given tactical style.
    Returns a score from 0.0 to 100.0.
    """
    if not player.capability_profile:
        return 50.0

    cap = player.capability_profile
    def score(name: str) -> float:
        val = getattr(cap, name)
        return val.score if val else 0.0

    if target_style == "Possession-Dominant":
        return (score("ball_security") * 0.40) + (score("ball_progression") * 0.30) + (score("press_resistance") * 0.30)
    
    if target_style == "High Press":
        return (score("defensive_activity") * 0.40) + (score("physical_availability") * 0.30) + (score("press_resistance") * 0.30)
    
    if target_style == "Direct and Progressive":
        return (score("ball_progression") * 0.45) + (score("chance_creation") * 0.35) + (score("attacking_threat") * 0.20)
    
    if target_style == "Counter-Attacking":
        return (score("attacking_threat") * 0.40) + (score("ball_progression") * 0.30) + (score("defensive_activity") * 0.30)
    
    if target_style == "Defensive and Resilient":
        return (score("defensive_activity") * 0.50) + (score("ball_security") * 0.30) + (score("physical_availability") * 0.20)
    
    # "Balanced" or unknown
    return (score("tactical_versatility") * 0.40) + (score("ball_security") * 0.30) + (score("defensive_activity") * 0.30)


def get_tactical_fit_explanation(player: PlayerProfile, target_style: str, fit_score: float) -> str:
    """Generate a brief explanation for the tactical fit score."""
    if fit_score >= 80:
        return f"Excellent fit for {target_style} system due to strong aligned capabilities."
    if fit_score >= 65:
        return f"Solid fit for {target_style} system."
    if fit_score >= 50:
        return f"Marginal fit for {target_style} system; some capability gaps exist."
    return f"Poor fit for {target_style} system; capabilities do not align."
