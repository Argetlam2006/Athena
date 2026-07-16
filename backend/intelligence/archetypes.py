"""
backend/intelligence/archetypes.py — Deterministic Playing Style Engine.

Derives Playing Style (Archetypes) from relative capability patterns
within positional cohorts, eliminating LLM inference.
"""

from __future__ import annotations
import pandas as pd
from typing import Sequence
from shared.schemas import PlayerProfile
from shared.config.capabilities import CORE_CAPABILITIES

def assign_archetypes(profiles: Sequence[PlayerProfile]) -> None:
    """
    Assign archetypes deterministically by computing capability percentiles 
    within position groups across the entire cohort.
    Mutates the profiles in-place to assign `archetype` and `archetype_description`.
    """
    if not profiles:
        return

    # Extract all relevant capability scores into a DataFrame
    data = []
    for i, p in enumerate(profiles):
        row = {
            "index": i,
            "position_group": p.position_group,
            "minutes_played": p.minutes_played or 0.0
        }
        if p.capability_profile:
            for cap in CORE_CAPABILITIES:
                cap_obj = getattr(p.capability_profile, cap)
                row[cap] = cap_obj.score if cap_obj else 0.0
        else:
            for cap in CORE_CAPABILITIES:
                row[cap] = 0.0
        data.append(row)

    df = pd.DataFrame(data)

    # Compute percentiles within position_group for all core capabilities
    pct_df = df.groupby('position_group')[CORE_CAPABILITIES].transform(
        lambda x: ((x.rank(method='average') - 0.5) / len(x) * 100.0).clip(0.0, 100.0)
    ).fillna(0.0)

    # Map deterministic patterns to archetypes based on relative percentiles
    for i, p in enumerate(profiles):
        row_pct = pct_df.iloc[i].to_dict()
        label, desc = _determine_archetype(row_pct, p.position_group, df.iloc[i].to_dict())
        p.archetype = label
        p.archetype_description = desc


def _determine_archetype(pct: dict[str, float], position: str, raw: dict[str, float]) -> tuple[str, str]:
    """
    Determine archetype using percentile scores relative to the positional cohort.
    """
    def is_elite(cap: str) -> bool:
        return pct.get(cap, 0.0) >= 80.0

    def is_strong(cap: str) -> bool:
        return pct.get(cap, 0.0) >= 65.0

    # Priorities mapped by combination of elite/strong relative traits
    if is_elite("attacking_threat"):
        return "Elite Goal Scorer", "Top tier direct goal threat compared to peers"
    
    if is_elite("chance_creation") and is_strong("ball_progression"):
        return "Creative Playmaker", "Elite chance creation combined with progressive passing"
    
    if is_elite("ball_security") and is_strong("ball_progression"):
        return "Deep-Lying Playmaker", "Elite ball retention with strong progressive passing"
    
    if is_strong("ball_progression") and is_strong("defensive_activity"):
        return "Box-to-Box Engine", "Contributes strongly in both progression and defensive phases relative to peers"
    
    if is_strong("ball_progression") and is_strong("chance_creation") and position == "Defender":
        return "Progressive Defender", "Attacking defender who drives forward and creates"
    
    if is_elite("defensive_activity") and is_strong("ball_security"):
        return "Defensive Specialist", "Elite defensive contribution with secure possession"
    
    if is_elite("press_resistance") and is_strong("ball_security"):
        return "Press-Resistant Anchor", "Maintains elite control when pressed aggressively"
    
    if is_elite("defensive_activity") and pct.get("press_resistance", 0.0) >= 65:
        return "High-Energy Presser", "Relentless defensively under pressure"

    # All-Round Contributor
    scores = list(pct.values())
    if all(s >= 30 for s in scores) and sum(1 for s in scores if s >= 60) >= 4:
        return "All-Round Contributor", "Well-rounded profile with no material weaknesses"

    # Developing Profile / Default
    return "Developing Profile", "Statistical profile does not highly index in any specific elite pattern"
