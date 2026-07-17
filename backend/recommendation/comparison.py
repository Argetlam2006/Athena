"""
backend/recommendation/comparison.py - Player Comparison Engine.

Compares two or more PlayerProfiles quantitatively across all 8 capabilities,
producing structured insights about similarities and differences.
"""

from __future__ import annotations

from shared.schemas import ComparisonResult, PlayerProfile


def _get_capability_score(player: PlayerProfile, capability: str) -> float:
    """Helper to safely extract a capability score."""
    if not player.capability_profile:
        return 0.0
    cap = getattr(player.capability_profile, capability)
    return cap.score if cap else 0.0


def compare_players(players: list[PlayerProfile]) -> ComparisonResult:
    """
    Compare multiple players across all capabilities.
    Generates structured strengths, differences, and a summary.
    """
    if not players:
        return ComparisonResult(players=[])

    from shared.config.capabilities import CORE_CAPABILITIES

    capabilities = CORE_CAPABILITIES

    cap_comparison: dict[str, dict[str, float]] = {}

    # 1. Build Capability Comparison Matrix
    for cap in capabilities:
        cap_comparison[cap] = {}
        for p in players:
            cap_comparison[cap][p.player_name] = _get_capability_score(p, cap)

    shared_strengths = []
    key_differences = []

    if len(players) >= 2:
        # Generate Insights for pairwise or group
        # Shared Strengths: All players > 70
        for cap in capabilities:
            scores = list(cap_comparison[cap].values())
            if all(s >= 70 for s in scores):
                shared_strengths.append(f"Strong {cap.replace('_', ' ').title()}")

        # Key Differences: Max difference > 15
        for cap in capabilities:
            scores = list(cap_comparison[cap].values())
            max_score = max(scores)
            min_score = min(scores)
            if max_score - min_score > 15:
                # Find who has max and min
                best_player = [
                    name for name, s in cap_comparison[cap].items() if s == max_score
                ][0]
                worst_player = [
                    name for name, s in cap_comparison[cap].items() if s == min_score
                ][0]
                diff_text = f"{cap.replace('_', ' ').title()}: {best_player} ({max_score:.1f}) outperforms {worst_player} ({min_score:.1f})"
                key_differences.append(diff_text)

    summary = f"Comparison of {', '.join(p.player_name for p in players)}. "
    if shared_strengths:
        summary += (
            "They share elite output in "
            + ", ".join([s.replace("Strong ", "").lower() for s in shared_strengths])
            + ". "
        )
    if key_differences:
        summary += "However, they differ significantly in specific tactical phases."
    else:
        summary += "Their profiles are statistically very similar across all domains."

    return ComparisonResult(
        players=players,
        shared_strengths=shared_strengths,
        key_differences=key_differences,
        capability_comparison=cap_comparison,
        recommendation_summary=summary.strip(),
    )
