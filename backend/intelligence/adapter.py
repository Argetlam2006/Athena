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

    # Fill NA with 0.0 for all metrics except the contextual ones which can be legitimately missing
    cols_to_fill = [c for c in df.columns if c not in ('minutes_played', 'matches_played', 'birth_date')]
    df[cols_to_fill] = df[cols_to_fill].fillna(0.0)

    for _, row in df.iterrows():
        # Handle cases where position_played_count might not be in the view
        # We default to 1 if not present.
        positions_played_count = row.get("positions_played_count", 1)
        if pd.isna(positions_played_count):
            positions_played_count = 1

        # Age calculation
        birth_date = row.get("birth_date")
        bd_str = None
        if pd.notna(birth_date):
            bd_str = str(birth_date).split(" ")[0]

        mins = row.get("minutes_played")
        minutes_played = None if pd.isna(mins) else float(mins)

        matches = row.get("matches_played")
        matches_played = None if pd.isna(matches) else int(matches)

        vectors.append(
            PlayerFeatureVector(
                player_id=row.get("player_id", 0),
                player_name=row.get("player_name", "Unknown"),
                season=row.get("season_name", "Unknown"),
                competition=row.get("competition_name", "Unknown"),
                position_group=map_position_to_group(row.get("position_name")),
                minutes_played=minutes_played,
                matches_played=matches_played,
                team_name=row.get("team_name", "Unknown"),
                birth_date=bd_str,
                # Ball Progression
                progressive_passes_p90=row.get("progressive_passes_p90", 0.0),
                progressive_carries_p90=row.get("progressive_carries_p90", 0.0),
                carry_distance_p90=row.get("carry_distance_p90", 0.0),
                switches_p90=row.get("switches_p90", 0.0),
                # Chance Creation
                shot_assists_p90=row.get("shot_assists_p90", 0.0),
                goal_assists_p90=row.get("goal_assists_p90", 0.0),
                through_balls_p90=row.get("through_balls_p90", 0.0),
                crosses_p90=row.get("crosses_p90", 0.0),
                # Ball Security
                pass_accuracy_pct=row.get("pass_accuracy_pct", 0.0),
                dribble_success_pct=row.get("dribble_success_pct", 0.0),
                passes_p90=row.get("passes_p90", 0.0),
                avg_pass_length_m=row.get("avg_pass_length_m", 0.0),
                # Press Resistance
                pressure_pct=row.get("pressure_pct", 0.0),
                events_under_pressure_p90=row.get("events_under_pressure_p90", 0.0),
                # Defensive Activity
                pressures_p90=row.get("pressures_p90", 0.0),
                recoveries_p90=row.get("recoveries_p90", 0.0),
                clearances_p90=row.get("clearances_p90", 0.0),
                # Attacking Threat
                npxg_p90=row.get("npxg_p90", 0.0),
                goals_p90=row.get("goals_p90", 0.0),
                xg_per_shot=row.get("xg_per_shot", 0.0),
                shot_accuracy_pct=row.get("shot_accuracy_pct", 0.0),
                goals_minus_xg=row.get("goals_minus_xg", 0.0),
                # Contextual
                positions_played_count=int(positions_played_count),
            )
        )

    return vectors
