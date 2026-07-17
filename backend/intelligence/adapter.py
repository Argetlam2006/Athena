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
    if "center back" in pos:
        return "Center Back"
    if "back" in pos:
        return "Fullback"
    if "defensive midfield" in pos:
        return "Defensive Midfielder"
    if "attacking midfield" in pos:
        return "Attacking Midfielder"
    if "midfield" in pos:
        return "Central Midfielder"
    if "wing" in pos:
        return "Winger"
    if "forward" in pos or "striker" in pos:
        return "Center Forward"

    return "Unknown"


def map_player_summary_to_vectors(df: pd.DataFrame) -> list[PlayerFeatureVector]:
    """
    Convert a DataFrame from vw_player_summary into a list of PlayerFeatureVector objects.
    """
    vectors = []

    # Fill NA with 0.0 for all metrics except the contextual ones which can be legitimately missing
    cols_to_fill = [
        c
        for c in df.columns
        if c not in ("minutes_played", "matches_played", "birth_date")
    ]
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
                tackles_p90=row.get("tackles_p90", 0.0),
                tackles_won_p90=row.get("tackles_won_p90", 0.0),
                interceptions_p90=row.get("interceptions_p90", 0.0),
                dribbled_past_p90=row.get("dribbled_past_p90", 0.0),
                errors_leading_to_shot_p90=row.get("errors_leading_to_shot_p90", 0.0),
                aerials_won_p90=row.get("aerials_won_p90", 0.0),
                aerials_total_p90=row.get("aerials_total_p90", 0.0),
                # Attacking Threat
                npxg_p90=row.get("npxg_p90", 0.0),
                goals_p90=row.get("goals_p90", 0.0),
                xg_per_shot=row.get("xg_per_shot", 0.0),
                shot_accuracy_pct=row.get("shot_accuracy_pct", 0.0),
                goals_minus_xg=row.get("goals_minus_xg", 0.0),
                # Contextual
                positions_played_count=int(positions_played_count),
                raw_metrics={
                    "goals": int(row.get("goals", 0)),
                    "goal_assists": int(row.get("goal_assists", 0)),
                    "shot_assists": int(row.get("shot_assists", 0)),
                    "total_shots": int(row.get("total_shots", 0)),
                    "shots_on_target": int(row.get("shots_on_target", 0)),
                    "total_passes": int(row.get("total_passes", 0)),
                    "accurate_passes": int(row.get("accurate_passes", 0)),
                    "progressive_passes": int(row.get("progressive_passes", 0)),
                    "progressive_carries": int(row.get("progressive_carries", 0)),
                    "total_carries": int(row.get("total_carries", 0)),
                    "total_dribbles": int(row.get("total_dribbles", 0)),
                    "dribbles_completed": int(row.get("dribbles_completed", 0)),
                    "pressures": int(row.get("pressures", 0)),
                    "ball_recoveries": int(row.get("ball_recoveries", 0)),
                    "clearances": int(row.get("clearances", 0)),
                    "tackles": int(row.get("tackles", 0)),
                    "interceptions": int(row.get("interceptions", 0)),
                    "aerials_won": int(row.get("aerials_won", 0)),
                    "aerials_total": int(row.get("aerials_total", 0)),
                    "xg_total": float(row.get("xg_total", 0.0)),
                    "npxg_total": float(row.get("npxg_total", 0.0)),
                },
            )
        )

    return vectors
