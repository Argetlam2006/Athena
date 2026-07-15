"""
shared/config/capabilities.py — Capability and metric definitions.
"""

from typing import Any

CAPABILITIES: list[str] = [
    "ball_progression",
    "chance_creation",
    "ball_security",
    "press_resistance",
    "defensive_activity",
    "attacking_threat",
    "physical_availability",
    "tactical_versatility",
]

CAPABILITY_DISPLAY_NAMES: dict[str, str] = {
    "ball_progression": "Ball Progression",
    "chance_creation": "Chance Creation",
    "ball_security": "Ball Security",
    "press_resistance": "Press Resistance",
    "defensive_activity": "Defensive Activity",
    "attacking_threat": "Attacking Threat",
    "physical_availability": "Physical Availability",
    "tactical_versatility": "Tactical Versatility",
}

CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "ball_progression": "Ability to advance possession into valuable areas.",
    "chance_creation": "Ability to create attacking opportunities for teammates.",
    "ball_security": "Ability to maintain possession and minimise turnovers.",
    "press_resistance": "Ability to remain effective under defensive pressure.",
    "defensive_activity": "Ability to disrupt opposition possession and win the ball back.",
    "attacking_threat": "Ability to generate dangerous attacking outcomes and score.",
    "physical_availability": "Ability to contribute consistently across a full season.",
    "tactical_versatility": "Ability to perform effectively across multiple positions and roles.",
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
    ],
    "attacking_threat": [
        "npxg_p90",
        "goals_p90",
        "xg_per_shot",
        "shot_accuracy_pct",
        "goals_minus_xg",
    ],
    "physical_availability": [
        "matches_played",
        "minutes_played",
    ],
    "tactical_versatility": [
        "positions_played_count",
    ],
}

# Nested dictionary: capability -> metric -> weight
# For positions requiring overrides, we use a dictionary structure for weights.
CAPABILITY_METRIC_WEIGHTS: dict[str, Any] = {
    "ball_progression": {
        "progressive_passes_p90": 0.35,
        "progressive_carries_p90": 0.35,
        "carry_distance_p90": 0.15,
        "switches_p90": 0.15,
    },
    "chance_creation": {
        "default": {
            "shot_assists_p90": 0.40,
            "goal_assists_p90": 0.30,
            "through_balls_p90": 0.20,
            "crosses_p90": 0.10,
        },
        "wide": {
            "shot_assists_p90": 0.35,
            "goal_assists_p90": 0.25,
            "through_balls_p90": 0.15,
            "crosses_p90": 0.25,
        }
    },
    "ball_security": {
        "pass_accuracy_pct": 0.50,
        "dribble_success_pct": 0.25,
        "passes_p90": 0.15,
        "avg_pass_length_m": 0.10,
    },
    "press_resistance": {
        "pressure_pct": 0.50,
        "events_under_pressure_p90": 0.50, # Simplified proxy for V1 since pass accuracy proxy was rejected
    },
    "defensive_activity": {
        "default": {
            "pressures_p90": 0.45,
            "recoveries_p90": 0.35,
            "clearances_p90": 0.20,
        },
        "Defender": {
            "pressures_p90": 0.35,
            "recoveries_p90": 0.35,
            "clearances_p90": 0.30,
        },
        "Forward": {
            "pressures_p90": 0.55,
            "recoveries_p90": 0.35,
            "clearances_p90": 0.10,
        }
    },
    "attacking_threat": {
        "npxg_p90": 0.35,
        "goals_p90": 0.25,
        "xg_per_shot": 0.20,
        "shot_accuracy_pct": 0.15,
        "goals_minus_xg": 0.05,
    },
    # These are handled specifically in the Intelligence Engine rather than naive weighted sums
    "physical_availability": {
        "matches_played": 0.40,
        "coverage_rate": 0.60,
    },
    "tactical_versatility": {
        "positions_played_count": 0.25,
        "capability_breadth": 0.40,
        "phase_balance": 0.35,
    }
}

# The weights to combine capabilities into the Overall Profile.
POSITION_GROUP_WEIGHTS: dict[str, dict[str, float]] = {
    "Forward": {
        "ball_progression": 0.10,
        "chance_creation": 0.20,
        "ball_security": 0.08,
        "press_resistance": 0.10,
        "defensive_activity": 0.07,
        "attacking_threat": 0.28,
        "physical_availability": 0.10,
        "tactical_versatility": 0.07,
    },
    "Midfielder": {
        "ball_progression": 0.18,
        "chance_creation": 0.15,
        "ball_security": 0.15,
        "press_resistance": 0.15,
        "defensive_activity": 0.13,
        "attacking_threat": 0.08,
        "physical_availability": 0.10,
        "tactical_versatility": 0.06,
    },
    "Defender": {
        "ball_progression": 0.12,
        "chance_creation": 0.07,
        "ball_security": 0.18,
        "press_resistance": 0.12,
        "defensive_activity": 0.25,
        "attacking_threat": 0.05,
        "physical_availability": 0.13,
        "tactical_versatility": 0.08,
    }
}
