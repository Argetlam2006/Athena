"""
backend/intelligence/archetypes.py — Deterministic Playing Style Engine.

Derives Playing Style (Archetypes) using Cosine Similarity and Euclidean Distance
against predefined ideal capability vectors.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pandas as pd

from shared.config.capabilities import CORE_CAPABILITIES
from shared.schemas import ArchetypeProfile, PlayerProfile

# Define ideal vectors (0-100 scale) for each positional group.
# These represent the "platonic ideal" of a specific playing style.
ARCHETYPE_TEMPLATES: dict[str, dict[str, dict[str, float]]] = {
    "Center Forward": {
        "Elite Goal Scorer": {
            "ball_progression": 40.0,
            "chance_creation": 50.0,
            "ball_security": 50.0,
            "press_resistance": 50.0,
            "defensive_activity": 30.0,
            "attacking_threat": 100.0,
        },
        "Complete Forward": {
            "ball_progression": 75.0,
            "chance_creation": 80.0,
            "ball_security": 80.0,
            "press_resistance": 80.0,
            "defensive_activity": 60.0,
            "attacking_threat": 90.0,
        },
        "Target Man": {
            "ball_progression": 40.0,
            "chance_creation": 60.0,
            "ball_security": 60.0,
            "press_resistance": 90.0,
            "defensive_activity": 40.0,
            "attacking_threat": 80.0,
        },
    },
    "Winger": {
        "Creative Winger": {
            "ball_progression": 85.0,
            "chance_creation": 90.0,
            "ball_security": 75.0,
            "press_resistance": 70.0,
            "defensive_activity": 40.0,
            "attacking_threat": 75.0,
        },
        "Direct Winger": {
            "ball_progression": 90.0,
            "chance_creation": 60.0,
            "ball_security": 70.0,
            "press_resistance": 65.0,
            "defensive_activity": 45.0,
            "attacking_threat": 85.0,
        },
    },
    "Attacking Midfielder": {
        "Creative Playmaker": {
            "ball_progression": 90.0,
            "chance_creation": 100.0,
            "ball_security": 85.0,
            "press_resistance": 80.0,
            "defensive_activity": 40.0,
            "attacking_threat": 70.0,
        },
    },
    "Central Midfielder": {
        "Deep-Lying Playmaker": {
            "ball_progression": 100.0,
            "chance_creation": 70.0,
            "ball_security": 100.0,
            "press_resistance": 80.0,
            "defensive_activity": 60.0,
            "attacking_threat": 30.0,
        },
        "Box-to-Box Engine": {
            "ball_progression": 80.0,
            "chance_creation": 60.0,
            "ball_security": 75.0,
            "press_resistance": 75.0,
            "defensive_activity": 80.0,
            "attacking_threat": 60.0,
        },
    },
    "Defensive Midfielder": {
        "Press-Resistant Anchor": {
            "ball_progression": 70.0,
            "chance_creation": 40.0,
            "ball_security": 90.0,
            "press_resistance": 100.0,
            "defensive_activity": 85.0,
            "attacking_threat": 20.0,
        },
        "Midfield Destroyer": {
            "ball_progression": 50.0,
            "chance_creation": 30.0,
            "ball_security": 70.0,
            "press_resistance": 70.0,
            "defensive_activity": 95.0,
            "attacking_threat": 10.0,
        },
    },
    "Fullback": {
        "Progressive Fullback": {
            "ball_progression": 90.0,
            "chance_creation": 80.0,
            "ball_security": 75.0,
            "press_resistance": 70.0,
            "defensive_activity": 70.0,
            "attacking_threat": 50.0,
        },
        "Defensive Fullback": {
            "ball_progression": 60.0,
            "chance_creation": 40.0,
            "ball_security": 75.0,
            "press_resistance": 70.0,
            "defensive_activity": 85.0,
            "attacking_threat": 20.0,
        },
    },
    "Center Back": {
        "Ball-Playing Defender": {
            "ball_progression": 90.0,
            "chance_creation": 50.0,
            "ball_security": 90.0,
            "press_resistance": 80.0,
            "defensive_activity": 85.0,
            "attacking_threat": 20.0,
        },
        "Traditional Defender": {
            "ball_progression": 50.0,
            "chance_creation": 20.0,
            "ball_security": 70.0,
            "press_resistance": 60.0,
            "defensive_activity": 100.0,
            "attacking_threat": 10.0,
        },
    },
    "Goalkeeper": {},
}


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot_product / (mag1 * mag2)


def _euclidean_similarity(v1: list[float], v2: list[float], max_dist: float) -> float:
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2, strict=False)))
    return max(0.0, 1.0 - (dist / max_dist))


def assign_archetypes(profiles: Sequence[PlayerProfile]) -> None:
    """
    Assign archetypes deterministically using a style-first similarity metric.
    Computes percentiles first (so archetypes represent relative cohort dominance),
    then matches against the ideal capability vectors.
    """
    if not profiles:
        return

    # 1. Extract capabilities into a DataFrame for percentile calculation
    data = []
    for i, p in enumerate(profiles):
        row = {
            "index": i,
            "position_group": p.position_group,
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

    # 2. Compute percentiles relative to positional peers
    pct_df = (
        df.groupby("position_group")[CORE_CAPABILITIES]
        .transform(
            lambda x: ((x.rank(method="average") - 0.5) / len(x) * 100.0).clip(
                0.0, 100.0
            )
        )
        .fillna(0.0)
    )

    max_euclidean_dist = math.sqrt(len(CORE_CAPABILITIES) * (100.0**2))

    # 3. Match against Archetype Templates
    for i, p in enumerate(profiles):
        pos_group = p.position_group
        templates = ARCHETYPE_TEMPLATES.get(pos_group)
        if pos_group == "Goalkeeper":
            p.archetype_profile = ArchetypeProfile(
                primary_archetype="Goalkeeper", confidence=1.0
            )
            continue

        if not templates:
            # Flatten all templates for cross-position matching if position is Unknown
            templates = {}
            for pos_templates in ARCHETYPE_TEMPLATES.values():
                templates.update(pos_templates)

        player_vector = [pct_df.iloc[i][cap] for cap in CORE_CAPABILITIES]

        # If the player has literal 0s everywhere (no data), fallback
        if sum(player_vector) == 0:
            p.archetype_profile = ArchetypeProfile(
                primary_archetype="Unknown",
                confidence=0.0,
                alternatives=[],
                contributing_capabilities=[],
            )
            continue

        similarities = []
        for arch_name, arch_dict in templates.items():
            arch_vector = [arch_dict[cap] for cap in CORE_CAPABILITIES]

            cos_sim = _cosine_similarity(player_vector, arch_vector)
            euc_sim = _euclidean_similarity(
                player_vector, arch_vector, max_euclidean_dist
            )

            # Blend: 75% Cosine (Style), 25% Euclidean (Magnitude)
            final_sim = (cos_sim * 0.75) + (euc_sim * 0.25)
            similarities.append((arch_name, final_sim))

        # Sort by highest similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        primary_name, primary_sim = similarities[0]

        # If the highest similarity is extremely low (< 0.3), fallback to Unknown
        if primary_sim < 0.3:
            p.archetype_profile = ArchetypeProfile(
                primary_archetype="Unknown",
                confidence=0.0,
                alternatives=[],
                contributing_capabilities=[],
            )
            continue

        # Confidence is derived directly from the similarity score to make it continuous
        primary_conf = round(primary_sim * 100.0, 1)

        alternatives = [
            (name, round(score * 100.0, 1)) for name, score in similarities[1:3]
        ]

        # Calculate top contributing capabilities for the primary match
        # (Where the player's percentile is highest AND the archetype demands it)
        primary_template = templates[primary_name]
        contributions = []
        for cap in CORE_CAPABILITIES:
            player_val = pct_df.iloc[i][cap]
            template_val = primary_template[cap]
            # Contribution is product of player's relative strength and template's requirement
            contributions.append((cap, player_val * template_val))

        contributions.sort(key=lambda x: x[1], reverse=True)
        top_caps = [c[0].replace("_", " ").title() for c in contributions[:3]]

        p.archetype_profile = ArchetypeProfile(
            primary_archetype=primary_name,
            confidence=primary_conf,
            alternatives=alternatives,
            contributing_capabilities=top_caps,
        )
