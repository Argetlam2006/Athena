"""
shared/config/capabilities.py — Capability and metric definitions.
"""

from typing import Any

CORE_CAPABILITIES: list[str] = [
    "ball_progression",
    "chance_creation",
    "ball_security",
    "press_resistance",
    "defensive_activity",
    "attacking_threat",
]

CAPABILITY_DISPLAY_NAMES: dict[str, str] = {
    "ball_progression": "Ball Progression",
    "chance_creation": "Chance Creation",
    "ball_security": "Ball Security",
    "press_resistance": "Press Resistance",
    "defensive_activity": "Defensive Activity",
    "attacking_threat": "Attacking Threat",
}

CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "ball_progression": "Ability to advance possession into valuable areas.",
    "chance_creation": "Ability to create attacking opportunities for teammates.",
    "ball_security": "Ability to maintain possession and minimise turnovers.",
    "press_resistance": "Ability to remain effective under defensive pressure.",
    "defensive_activity": "Ability to disrupt opposition possession and win the ball back.",
    "attacking_threat": "Ability to generate dangerous attacking outcomes and score.",
}

# The metric map maps capability name to the attributes in PlayerFeatureVector.
CAPABILITY_METRIC_MAP: dict[str, list[str]] = {
    "ball_progression": [
        "progressive_passes_p90",
        "progressive_carries_p90",
        "carry_distance_p90",
        "switches_p90",
    ],
    "chance_creation": [
        "shot_assists_p90",
        "goal_assists_p90",
        "through_balls_p90",
        "crosses_p90",
    ],
    "ball_security": [
        "pass_accuracy_pct",
        "dribble_success_pct",
        "passes_p90",
        "avg_pass_length_m",
    ],
    "press_resistance": [
        "pressure_pct",
        "events_under_pressure_p90",
    ],
    "defensive_activity": [
        "pressures_p90",
        "recoveries_p90",
        "clearances_p90",
        "tackles_p90",
        "interceptions_p90",
        "tackles_won_p90",
    ],
    "attacking_threat": [
        "npxg_p90",
        "goals_p90",
        "xg_per_shot",
        "shot_accuracy_pct",
        "goals_minus_xg",
    ],
}

# The weights determining how heavily each primitive metric contributes to its parent Capability.
# Some capabilities change weight depending on the player's position.
CAPABILITY_METRIC_WEIGHTS: dict[str, dict[str, dict[str, float]] | dict[str, float]] = {
    "ball_progression": {
        "progressive_passes_p90": 0.40,
        "progressive_carries_p90": 0.35,
        "carry_distance_p90": 0.15,
        "switches_p90": 0.10,
    },
    "chance_creation": {
        "shot_assists_p90": 0.45,
        "goal_assists_p90": 0.25,
        "through_balls_p90": 0.20,
        "crosses_p90": 0.10,
    },
    "ball_security": {
        "default": {
            "pass_accuracy_pct": 0.35,
            "dribble_success_pct": 0.15,
            "passes_p90": 0.40,
            "avg_pass_length_m": 0.10,
        },
        "Defender": {
            "pass_accuracy_pct": 0.40,
            "dribble_success_pct": 0.05,
            "passes_p90": 0.45,
            "avg_pass_length_m": 0.10,
        },
    },
    "press_resistance": {
        "pressure_pct": 0.50,
        "events_under_pressure_p90": 0.50,  # Simplified proxy for V1 since pass accuracy proxy was rejected
    },
    "defensive_activity": {
        "active": {
            "pressures_p90": 0.25,
            "recoveries_p90": 0.25,
            "tackles_p90": 0.25,
            "interceptions_p90": 0.25,
        },
        "controlling": {
            "clearances_p90": 0.20,
            "tackles_won_p90": 0.20,
            "aerials_won_p90": 0.30,
            "dribbled_past_p90": 0.15,
            "errors_leading_to_shot_p90": 0.15,
        }
    },
    "attacking_threat": {
        "npxg_p90": 0.35,
        "goals_p90": 0.25,
        "xg_per_shot": 0.20,
        "shot_accuracy_pct": 0.15,
        "goals_minus_xg": 0.05,
    },
}

# The weights to combine capabilities into the Overall Profile.
POSITION_GROUP_WEIGHTS: dict[str, dict[str, float]] = {
    "Forward": {
        "ball_progression": 0.12,
        "chance_creation": 0.24,
        "ball_security": 0.10,
        "press_resistance": 0.12,
        "defensive_activity": 0.08,
        "attacking_threat": 0.34,
    },
    "Midfielder": {
        "ball_progression": 0.21,
        "chance_creation": 0.18,
        "ball_security": 0.18,
        "press_resistance": 0.18,
        "defensive_activity": 0.15,
        "attacking_threat": 0.10,
    },
    "Defender": {
        "ball_progression": 0.15,
        "chance_creation": 0.09,
        "ball_security": 0.23,
        "press_resistance": 0.15,
        "defensive_activity": 0.32,
        "attacking_threat": 0.06,
    },
}
