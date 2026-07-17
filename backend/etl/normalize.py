"""
backend/etl/normalize.py — StatsBomb JSON → typed pandas DataFrames

This module is the analytical core of the ETL pipeline.

Each function receives raw StatsBomb JSON (a list of dicts, as saved in
data/raw/) and returns a clean, fully-typed DataFrame ready for Parquet
export and downstream SQL analysis.

Design decisions:
  - Explicit field extraction over pd.json_normalize().
    This makes the schema self-documenting, failures easy to trace,
    and the code readable by anyone who understands StatsBomb data.
  - Nullable integer types (pd.Int64Dtype) for IDs and foreign keys.
  - Booleans default to False rather than None for flag columns.
  - Event columns are in wide format: one row per event, type-specific
    attributes (pass, shot, carry, dribble) in named columns.
    Null where the event type does not apply.

StatsBomb Open Data: CC BY-SA 4.0 — https://github.com/statsbomb/open-data
"""

from __future__ import annotations

import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _get(obj: dict | None, *keys: str, default=None):
    """
    Safe nested dictionary access.

    Examples:
        _get(event, "pass", "recipient", "id")   → int | None
        _get(event, "shot", "outcome", "name")   → str | None
    """
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key, default)
        if cur is None:
            return default
    return cur


def _loc_x(location: list | None) -> float | None:
    """Extract x coordinate from [x, y] or [x, y, z] location list."""
    return (
        float(location[0])
        if isinstance(location, list) and len(location) >= 1
        else None
    )


def _loc_y(location: list | None) -> float | None:
    """Extract y coordinate from [x, y] or [x, y, z] location list."""
    return (
        float(location[1])
        if isinstance(location, list) and len(location) >= 2
        else None
    )


# ─────────────────────────────────────────────────────────────────────────────
# Event sub-type extractors
# Each returns a flat dict of columns for one event dict.
# Returns Nones for all columns when the event type doesn't match.
# ─────────────────────────────────────────────────────────────────────────────


def _extract_pass(event: dict) -> dict:
    """Extract pass-specific columns."""
    p = event.get("pass") or {}
    end = p.get("end_location")
    return {
        "pass_length": p.get("length"),
        "pass_angle": p.get("angle"),
        "pass_end_x": _loc_x(end),
        "pass_end_y": _loc_y(end),
        "pass_recipient_id": _get(p, "recipient", "id"),
        "pass_recipient_name": _get(p, "recipient", "name"),
        "pass_height": _get(p, "height", "name"),
        "pass_type": _get(p, "type", "name"),
        "pass_outcome": _get(p, "outcome", "name"),
        "pass_switch": bool(p.get("switch")),
        "pass_through_ball": bool(p.get("through_ball")),
        "pass_shot_assist": bool(p.get("shot_assist")),
        "pass_goal_assist": bool(p.get("goal_assist")),
        "pass_cross": bool(p.get("cross")),
    }


def _extract_shot(event: dict) -> dict:
    """Extract shot-specific columns."""
    s = event.get("shot") or {}
    end = s.get("end_location")
    return {
        "shot_statsbomb_xg": s.get("statsbomb_xg"),
        "shot_end_x": _loc_x(end),
        "shot_end_y": _loc_y(end),
        "shot_end_z": float(end[2])
        if isinstance(end, list) and len(end) >= 3
        else None,
        "shot_outcome": _get(s, "outcome", "name"),
        "shot_type": _get(s, "type", "name"),
        "shot_technique": _get(s, "technique", "name"),
        "shot_body_part": _get(s, "body_part", "name"),
        "shot_first_time": bool(s.get("first_time")),
        "shot_one_on_one": bool(s.get("one_on_one")),
    }


def _extract_carry(event: dict) -> dict:
    """Extract carry-specific columns."""
    c = event.get("carry") or {}
    end = c.get("end_location")
    return {
        "carry_end_x": _loc_x(end),
        "carry_end_y": _loc_y(end),
    }


def _extract_dribble(event: dict) -> dict:
    """Extract dribble-specific columns."""
    d = event.get("dribble") or {}
    return {
        "dribble_outcome": _get(d, "outcome", "name"),
        "dribble_overrun": bool(d.get("overrun")),
        "dribble_nutmeg": bool(d.get("nutmeg")),
    }


def _null_pass() -> dict:
    return dict.fromkeys(_extract_pass({}))


def _null_shot() -> dict:
    return dict.fromkeys(_extract_shot({}))


def _null_carry() -> dict:
    return dict.fromkeys(_extract_carry({}))


def _null_dribble() -> dict:
    return dict.fromkeys(_extract_dribble({}))

def _extract_duel(event: dict) -> dict:
    """Extract duel-specific columns."""
    d = event.get("duel") or {}
    return {
        "duel_type": _get(d, "type", "name"),
        "duel_outcome": _get(d, "outcome", "name"),
    }

def _null_duel() -> dict:
    return dict.fromkeys(_extract_duel({}))

def _extract_interception(event: dict) -> dict:
    """Extract interception-specific columns."""
    i = event.get("interception") or {}
    return {
        "interception_outcome": _get(i, "outcome", "name"),
    }

def _null_interception() -> dict:
    return dict.fromkeys(_extract_interception({}))


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def normalize_competitions(data: list[dict]) -> pd.DataFrame:
    """
    Normalize raw competitions.json into a clean DataFrame.

    Input  : list of competition dicts from data/raw/competitions.json
    Output : DataFrame with one row per competition-season combination

    Columns:
        competition_id, competition_name, country_name,
        season_id, season_name, competition_gender
    """
    if not data:
        return pd.DataFrame()

    rows = [
        {
            "competition_id": int(c["competition_id"]),
            "competition_name": str(c["competition_name"]),
            "country_name": str(c.get("country_name", "")),
            "season_id": int(c["season_id"]),
            "season_name": str(c["season_name"]),
            "competition_gender": str(c.get("competition_gender", "male")),
        }
        for c in data
    ]

    df = pd.DataFrame(rows)
    df = df.astype(
        {
            "competition_id": "Int64",
            "season_id": "Int64",
        }
    )
    return df.sort_values(["competition_name", "season_name"]).reset_index(drop=True)


def normalize_matches(data: list[dict]) -> pd.DataFrame:
    """
    Normalize matches/{competition_id}/{season_id}.json into a clean DataFrame.

    Flattens the nested home_team, away_team, competition, season, stadium,
    and referee objects into top-level columns.

    Input  : list of match dicts from one matches/*.json file
    Output : DataFrame with one row per match

    Key columns:
        match_id, match_date, competition_id, season_id,
        home_team_id, home_team_name, away_team_id, away_team_name,
        home_score, away_score, match_week, stadium_name, referee_name
    """
    if not data:
        return pd.DataFrame()

    rows = []
    for m in data:
        rows.append(
            {
                "match_id": int(m["match_id"]),
                "match_date": m.get("match_date"),
                "kick_off": m.get("kick_off"),
                "match_week": m.get("match_week"),
                # Competition and season
                "competition_id": _get(m, "competition", "competition_id"),
                "competition_name": _get(m, "competition", "competition_name"),
                "season_id": _get(m, "season", "season_id"),
                "season_name": _get(m, "season", "season_name"),
                # Teams
                "home_team_id": _get(m, "home_team", "home_team_id"),
                "home_team_name": _get(m, "home_team", "home_team_name"),
                "away_team_id": _get(m, "away_team", "away_team_id"),
                "away_team_name": _get(m, "away_team", "away_team_name"),
                # Score
                "home_score": m.get("home_score"),
                "away_score": m.get("away_score"),
                # Metadata
                "stadium_name": _get(m, "stadium", "name"),
                "referee_name": _get(m, "referee", "name"),
                "match_status": m.get("match_status"),
            }
        )

    df = pd.DataFrame(rows)
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce").dt.date
    df = df.astype(
        {
            "match_id": "Int64",
            "competition_id": "Int64",
            "season_id": "Int64",
            "home_team_id": "Int64",
            "away_team_id": "Int64",
            "home_score": "Int64",
            "away_score": "Int64",
            "match_week": "Int64",
        }
    )
    return df.sort_values("match_id").reset_index(drop=True)


def normalize_events(data: list[dict], match_id: int) -> pd.DataFrame:
    """
    Normalize events/{match_id}.json into a wide-format analytical DataFrame.

    Each event type (Pass, Shot, Carry, Dribble, etc.) stores its type-specific
    attributes in prefixed columns. Columns are null where the event type
    doesn't apply, keeping the schema flat and SQL-friendly.

    Input  : list of event dicts from data/raw/events/{match_id}.json
             match_id: integer match ID (added as foreign key)
    Output : DataFrame with one row per event (~1 500–3 500 rows per match)

    Core columns (all events):
        event_id, match_id, index, period, timestamp, minute, second,
        type_id, type_name, play_pattern, team_id, team_name,
        player_id, player_name, position_name, location_x, location_y,
        duration, under_pressure

    Pass columns  (when type_name == "Pass"):
        pass_length, pass_angle, pass_end_x/y, pass_recipient_id/name,
        pass_height, pass_type, pass_outcome, pass_switch,
        pass_through_ball, pass_shot_assist, pass_goal_assist, pass_cross

    Shot columns  (when type_name == "Shot"):
        shot_statsbomb_xg, shot_end_x/y/z, shot_outcome, shot_type,
        shot_technique, shot_body_part, shot_first_time, shot_one_on_one

    Carry columns (when type_name == "Carry"):
        carry_end_x, carry_end_y

    Dribble columns (when type_name == "Dribble"):
        dribble_outcome, dribble_overrun, dribble_nutmeg
    """
    if not data:
        return pd.DataFrame()

    rows = []
    for e in data:
        type_name = _get(e, "type", "name") or ""
        location = e.get("location")

        # Core event fields — present in every event
        row: dict = {
            "event_id": e["id"],
            "match_id": match_id,
            "index": e["index"],
            "period": e.get("period"),
            "timestamp": e.get("timestamp"),
            "minute": e.get("minute"),
            "second": e.get("second"),
            "type_id": _get(e, "type", "id"),
            "type_name": type_name,
            "play_pattern": _get(e, "play_pattern", "name"),
            "possession": e.get("possession"),
            "team_id": _get(e, "team", "id"),
            "team_name": _get(e, "team", "name"),
            "player_id": _get(e, "player", "id"),
            "player_name": _get(e, "player", "name"),
            "position_name": _get(e, "position", "name"),
            "location_x": _loc_x(location),
            "location_y": _loc_y(location),
            "duration": e.get("duration"),
            "under_pressure": bool(e.get("under_pressure")),
            "aerial_won": bool(
                _get(e, "pass", "aerial_won") or 
                _get(e, "clearance", "aerial_won") or 
                _get(e, "shot", "aerial_won") or 
                _get(e, "miscontrol", "aerial_won")
            ),
        }

        # Type-specific attributes
        row.update(_extract_pass(e) if type_name == "Pass" else _null_pass())
        row.update(_extract_shot(e) if type_name == "Shot" else _null_shot())
        row.update(_extract_carry(e) if type_name == "Carry" else _null_carry())
        row.update(_extract_dribble(e) if type_name == "Dribble" else _null_dribble())
        row.update(_extract_duel(e) if type_name == "Duel" else _null_duel())
        row.update(_extract_interception(e) if type_name == "Interception" else _null_interception())

        rows.append(row)

    df = pd.DataFrame(rows)

    # Type enforcement
    int_cols = [
        "index",
        "period",
        "minute",
        "second",
        "type_id",
        "possession",
        "team_id",
        "player_id",
        "pass_recipient_id",
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    float_cols = [
        "location_x",
        "location_y",
        "duration",
        "pass_length",
        "pass_angle",
        "pass_end_x",
        "pass_end_y",
        "shot_statsbomb_xg",
        "shot_end_x",
        "shot_end_y",
        "shot_end_z",
        "carry_end_x",
        "carry_end_y",
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float32")

    df["match_id"] = match_id  # ensure int, not nullable

    return df.reset_index(drop=True)


def normalize_lineups(data: list[dict], match_id: int) -> pd.DataFrame:
    """
    Normalize lineups/{match_id}.json into a player-appearance DataFrame.

    Each row represents one player in one match for one team.
    The player's starting position is extracted from the positions list.

    Input  : list of two team dicts from data/raw/lineups/{match_id}.json
             match_id: integer match ID (added as foreign key)
    Output : DataFrame with one row per player per match

    Columns:
        match_id, team_id, team_name, player_id, player_name,
        player_nickname, jersey_number, birth_date, height_cm, weight_kg,
        country_id, country_name, starting_position, starting_position_id
    """
    if not data:
        return pd.DataFrame()

    rows = []
    for team in data:
        team_id = team.get("team_id")
        team_name = team.get("team_name", "")

        for player in team.get("lineup", []):
            # Identify starting position from the positions list
            positions = player.get("positions") or []
            start_pos = next(
                (p for p in positions if p.get("start_reason") == "Starting XI"), None
            )

            rows.append(
                {
                    "match_id": match_id,
                    "team_id": team_id,
                    "team_name": team_name,
                    "player_id": player.get("player_id"),
                    "player_name": player.get("player_name"),
                    "player_nickname": player.get("player_nickname"),
                    "jersey_number": player.get("jersey_number"),
                    "birth_date": player.get("birth_date"),
                    "height_cm": player.get("player_height"),
                    "weight_kg": player.get("player_weight"),
                    "country_id": _get(player, "country", "id"),
                    "country_name": _get(player, "country", "name"),
                    "starting_position": start_pos.get("position")
                    if start_pos
                    else None,
                    "starting_position_id": start_pos.get("position_id")
                    if start_pos
                    else None,
                }
            )

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["birth_date"] = pd.to_datetime(df["birth_date"], errors="coerce").dt.date
    df = df.astype(
        {
            "match_id": "Int64",
            "team_id": "Int64",
            "player_id": "Int64",
            "jersey_number": "Int64",
            "country_id": "Int64",
            "starting_position_id": "Int64",
        }
    )
    df["height_cm"] = pd.to_numeric(df["height_cm"], errors="coerce").astype("float32")
    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce").astype("float32")

    return df.sort_values(["team_id", "jersey_number"]).reset_index(drop=True)
