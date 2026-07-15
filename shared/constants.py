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

# Workspace configurations have been migrated to shared.config.navigation
