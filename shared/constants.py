"""
shared/constants.py — Athena canonical constants

This module is the single source of truth for:
  - Capability definitions and metadata
  - StatsBomb metric mappings
  - Position groupings
  - Data source configuration
  - AIF pipeline ordering

Import from here. Never redefine these values in other modules.
"""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Athena Intelligence Framework — 8 Core Capabilities
# ─────────────────────────────────────────────────────────────────────────────

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
    "ball_progression":     "Ball Progression",
    "chance_creation":      "Chance Creation",
    "ball_security":        "Ball Security",
    "press_resistance":     "Press Resistance",
    "defensive_activity":   "Defensive Activity",
    "attacking_threat":     "Attacking Threat",
    "physical_availability": "Physical Availability",
    "tactical_versatility": "Tactical Versatility",
}

CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "ball_progression": (
        "Ability to advance possession into valuable areas "
        "through passing and carrying."
    ),
    "chance_creation": (
        "Ability to create attacking opportunities for teammates."
    ),
    "ball_security": (
        "Ability to maintain possession and minimise turnovers."
    ),
    "press_resistance": (
        "Ability to remain effective under defensive pressure."
    ),
    "defensive_activity": (
        "Ability to disrupt opposition possession and win the ball back."
    ),
    "attacking_threat": (
        "Ability to generate dangerous attacking outcomes and score."
    ),
    "physical_availability": (
        "Ability to contribute consistently across a full season."
    ),
    "tactical_versatility": (
        "Ability to perform effectively across multiple positions and roles, "
        "adapting to different tactical systems."
    ),
}

# ─────────────────────────────────────────────────────────────────────────────
# StatsBomb event type → capability mapping
# Each capability is derived from the listed StatsBomb event/metric columns.
# These map to columns in the processed analytics feature store.
# ─────────────────────────────────────────────────────────────────────────────

CAPABILITY_METRIC_MAP: dict[str, list[str]] = {
    "ball_progression": [
        "progressive_passes_per90",
        "progressive_carries_per90",
        "deep_completions_per90",
        "final_third_entries_per90",
        "penalty_area_entries_per90",
    ],
    "chance_creation": [
        "key_passes_per90",
        "xa_per90",
        "shot_assists_per90",
        "through_balls_per90",
        "crosses_per90",
    ],
    "ball_security": [
        "pass_completion_pct",
        "turnovers_per90",          # inverted — lower is better
        "dispossessions_per90",     # inverted
        "miscontrols_per90",        # inverted
        "progressive_pass_accuracy",
    ],
    "press_resistance": [
        "progressive_carries_per90",
        "successful_dribbles_per90",
        "dribble_success_pct",
        "carries_into_final_third_per90",
    ],
    "defensive_activity": [
        "pressures_per90",
        "ball_recoveries_per90",
        "interceptions_per90",
        "blocks_per90",
        "counterpressures_per90",
    ],
    "attacking_threat": [
        "xg_per90",
        "touches_in_box_per90",
        "shot_quality_pct",
        "goals_per90",
        "shots_on_target_per90",
    ],
    "physical_availability": [
        "minutes_played",
        "matches_started",
        "availability_pct",     # minutes / (90 * matches in competition)
        "age_years",            # younger = higher future availability
    ],
    "tactical_versatility": [
        "positions_played_count",       # number of distinct positions played
        "primary_position_pct",         # time in primary position (inverted — lower = more versatile)
        "formation_appearances_count",  # number of distinct formations deployed in
        "performance_consistency_score",# std dev of capability scores across positions (inverted)
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# Capability weights for composite scoring (must sum to 1.0 per group)
# These represent the relative importance of each metric within its capability.
# ─────────────────────────────────────────────────────────────────────────────

CAPABILITY_METRIC_WEIGHTS: dict[str, dict[str, float]] = {
    "ball_progression": {
        "progressive_passes_per90":   0.30,
        "progressive_carries_per90":  0.30,
        "deep_completions_per90":     0.15,
        "final_third_entries_per90":  0.15,
        "penalty_area_entries_per90": 0.10,
    },
    "chance_creation": {
        "key_passes_per90":  0.25,
        "xa_per90":          0.35,
        "shot_assists_per90": 0.15,
        "through_balls_per90": 0.15,
        "crosses_per90":     0.10,
    },
    "ball_security": {
        "pass_completion_pct":        0.35,
        "turnovers_per90":            0.25,
        "dispossessions_per90":       0.20,
        "miscontrols_per90":          0.10,
        "progressive_pass_accuracy":  0.10,
    },
    "press_resistance": {
        "progressive_carries_per90":        0.30,
        "successful_dribbles_per90":        0.25,
        "dribble_success_pct":              0.30,
        "carries_into_final_third_per90":   0.15,
    },
    "defensive_activity": {
        "pressures_per90":         0.25,
        "ball_recoveries_per90":   0.25,
        "interceptions_per90":     0.25,
        "blocks_per90":            0.15,
        "counterpressures_per90":  0.10,
    },
    "attacking_threat": {
        "xg_per90":              0.35,
        "touches_in_box_per90":  0.25,
        "shot_quality_pct":      0.15,
        "goals_per90":           0.20,
        "shots_on_target_per90": 0.05,
    },
    "physical_availability": {
        "minutes_played":    0.40,
        "matches_started":   0.30,
        "availability_pct":  0.20,
        "age_years":         0.10,
    },
    "tactical_versatility": {
        "positions_played_count":        0.35,
        "primary_position_pct":          0.30,
        "formation_appearances_count":   0.20,
        "performance_consistency_score": 0.15,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Position groups — normalized from StatsBomb position names
# ─────────────────────────────────────────────────────────────────────────────

POSITION_GROUPS: dict[str, list[str]] = {
    "GK": ["Goalkeeper"],
    "CB": ["Center Back", "Left Center Back", "Right Center Back"],
    "FB": ["Left Back", "Right Back", "Left Wing Back", "Right Wing Back"],
    "DM": ["Defensive Midfield"],
    "CM": ["Center Midfield", "Left Center Midfield", "Right Center Midfield"],
    "AM": ["Attacking Midfield", "Left Attacking Midfield", "Right Attacking Midfield"],
    "WI": ["Left Wing", "Right Wing", "Left Midfield", "Right Midfield"],
    "ST": ["Center Forward", "Left Center Forward", "Right Center Forward", "Secondary Striker"],
}

POSITION_GROUP_DISPLAY: dict[str, str] = {
    "GK": "Goalkeeper",
    "CB": "Centre Back",
    "FB": "Full Back",
    "DM": "Defensive Midfielder",
    "CM": "Central Midfielder",
    "AM": "Attacking Midfielder",
    "WI": "Winger",
    "ST": "Striker",
}

# ─────────────────────────────────────────────────────────────────────────────
# Data source configuration
# ─────────────────────────────────────────────────────────────────────────────

DATA_SOURCES: dict[str, dict] = {
    "statsbomb": {
        "name": "StatsBomb Open Data",
        "url": "https://github.com/statsbomb/open-data",
        "license": "CC BY-SA 4.0",
        "version_1": True,
        "description": "Event-level football data — primary data source for V1",
    },
    "fbref": {
        "name": "FBref",
        "url": "https://fbref.com",
        "license": "Terms of Service",
        "version_1": False,
        "description": "Season-level aggregated statistics — planned for V2",
    },
    "transfermarkt": {
        "name": "Transfermarkt",
        "url": "https://www.transfermarkt.com",
        "license": "Terms of Service",
        "version_1": False,
        "description": "Market values and transfer history — planned for V2",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# StatsBomb competitions included in the Open Data (Version 1 scope)
# ─────────────────────────────────────────────────────────────────────────────

STATSBOMB_COMPETITIONS: dict[str, int] = {
    "La Liga":            11,
    "Champions League":   16,
    "FA Women's Super League": 37,
    "FIFA World Cup":     43,
    "NWSL":              49,
    "Premier League":     2,
    "North American Soccer League": 55,
    "Major League Soccer": 253,
    "UEFA Euro":          55,
    "Copa del Rey":       21,
}

# ─────────────────────────────────────────────────────────────────────────────
# Analytics configuration
# ─────────────────────────────────────────────────────────────────────────────

# Minimum minutes threshold for a player to be included in analytics
MIN_MINUTES_THRESHOLD: int = 450  # ~5 full matches

# Percentile computation — use position-relative percentiles
USE_POSITION_RELATIVE_PERCENTILES: bool = True

# Rolling average window (in matches) for trend analysis
ROLLING_AVERAGE_WINDOW: int = 5

# Capability score scale
CAPABILITY_SCORE_MIN: float = 0.0
CAPABILITY_SCORE_MAX: float = 100.0

# ─────────────────────────────────────────────────────────────────────────────
# AIF pipeline layer names (for logging and tracing)
# ─────────────────────────────────────────────────────────────────────────────

AIF_LAYERS: list[str] = [
    "football_events",
    "football_statistics",
    "football_capabilities",
    "player_intelligence",
    "team_intelligence",
    "decision_intelligence",
    "natural_language_intelligence",
]

# ─────────────────────────────────────────────────────────────────────────────
# Workspace names (used in navigation and routing)
# ─────────────────────────────────────────────────────────────────────────────

WORKSPACES: dict[str, dict] = {
    "dashboard": {
        "display": "Dashboard",
        "icon": "⬡",
        "question": "What deserves my attention?",
        "route": "/",
    },
    "player_intelligence": {
        "display": "Player Intelligence",
        "icon": "◈",
        "question": "What kind of player is this?",
        "route": "/player",
    },
    "team_intelligence": {
        "display": "Team Intelligence",
        "icon": "◉",
        "question": "How does this team play?",
        "route": "/team",
    },
    "recruitment": {
        "display": "Recruitment Intelligence",
        "icon": "◎",
        "question": "Who should we sign?",
        "route": "/recruitment",
    },
    "ask_athena": {
        "display": "Ask Athena",
        "icon": "◇",
        "question": "Help me understand.",
        "route": "/ask",
    },
}
