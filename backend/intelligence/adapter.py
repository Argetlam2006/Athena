"""
backend/intelligence/adapter.py — DataFrame to Feature Vector Mapper

Adapts the raw DuckDB DataFrame from the Warehouse into strictly typed
PlayerFeatureVector objects for the Football Intelligence Engine.
"""

from __future__ import annotations

import logging

import pandas as pd

from shared.schemas import PlayerFeatureVector

logger = logging.getLogger(__name__)


def map_position_to_group(position_name: str | None) -> str:
    """Map a StatsBomb specific position name to a generalized position group."""
    if not position_name or not isinstance(position_name, str):
        return "Unknown"

    pos = position_name.lower()
    if "goalkeeper" in pos:
        return "Goalkeeper"
    if "back" in pos:
        return "Defender"
    if "midfield" in pos:
        return "Midfielder"
    if "wing" in pos or "forward" in pos or "striker" in pos:
        return "Forward"

    return "Unknown"


def map_player_summary_to_vectors(df: pd.DataFrame) -> list[PlayerFeatureVector]:
    """
    Convert a DataFrame from vw_player_summary into a list of PlayerFeatureVector objects.
    """
    vectors = []

    # Pre-calculate required columns to avoid KeyErrors and handle defaults
    # Replace any NULLs (which become NaN/None in pandas) with 0.0 to satisfy schemas
    df = df.fillna(0.0)

    for _, row in df.iterrows():
        # Handle cases where position_played_count might not be in the view
        # We default to 1 if not present.
        positions_played_count = row.get("positions_played_count", 1)
        if pd.isna(positions_played_count):
            positions_played_count = 1

        # Age calculation
        birth_date = row.get("birth_date")
        age_years = 0.0
        if pd.notna(birth_date):
            try:
                birth_year = pd.to_datetime(birth_date).year
                season_str = str(row["season_name"])
                season_year = int(season_str.split("/")[0]) if "/" in season_str else int(season_str)
                age_years = float(season_year - birth_year)
            except Exception:
                pass

        vector = PlayerFeatureVector(
            player_id=int(row["player_id"]),
            player_name=str(row["player_name"]),
            season=str(row["season_name"]),
            competition=str(row["competition_name"]),
            position_group=map_position_to_group(row.get("position_name")),
            minutes_played=float(row["minutes_played"]),
            matches_played=int(row["matches_played"]),
            team_name=str(row.get("team_name", "")),
            age_years=age_years,

            # Ball Progression (4)
            progressive_passes_p90=float(row.get("progressive_passes_p90", 0.0)),
            progressive_carries_p90=float(row.get("progressive_carries_p90", 0.0)),
            carry_distance_p90=float(row.get("carry_distance_p90", 0.0)),
            switches_p90=float(row.get("switches_p90", 0.0)),

            # Chance Creation (4)
            shot_assists_p90=float(row.get("shot_assists_p90", 0.0)),
            goal_assists_p90=float(row.get("goal_assists_p90", 0.0)),
            through_balls_p90=float(row.get("through_balls_p90", 0.0)),
            crosses_p90=float(row.get("crosses_p90", 0.0)),

            # Ball Security (4)
            pass_accuracy_pct=float(row.get("pass_accuracy_pct", 0.0)),
            dribble_success_pct=float(row.get("dribble_success_pct", 0.0)),
            passes_p90=float(row.get("passes_p90", 0.0)),
            avg_pass_length_m=float(row.get("avg_pass_length_m", 0.0)),

            # Press Resistance (2)
            pressure_pct=float(row.get("pressure_pct", 0.0)),
            events_under_pressure_p90=float(row.get("events_under_pressure_p90", 0.0)),

            # Defensive Activity (3)
            pressures_p90=float(row.get("pressures_p90", 0.0)),
            recoveries_p90=float(row.get("recoveries_p90", 0.0)),
            clearances_p90=float(row.get("clearances_p90", 0.0)),

            # Attacking Threat (5)
            npxg_p90=float(row.get("npxg_p90", 0.0)),
            goals_p90=float(row.get("goals_p90", 0.0)),
            xg_per_shot=float(row.get("xg_per_shot", 0.0)),
            shot_accuracy_pct=float(row.get("shot_accuracy_pct", 0.0)),
            goals_minus_xg=float(row.get("goals_minus_xg", 0.0)),

            # Tactical Versatility (1)
            positions_played_count=int(positions_played_count),
        )
        vectors.append(vector)

    return vectors
