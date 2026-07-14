"""
tests/test_etl.py — Unit tests for the ETL normalization functions

Tests normalize_competitions, normalize_matches, normalize_events, and
normalize_lineups using synthetic StatsBomb-format fixtures.

Philosophy: tests that prove the normalization logic is correct — not
exhaustive field-by-field coverage, but meaningful assertions on schema,
types, and the non-obvious transformation decisions.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from backend.etl.normalize import (
    _get,
    normalize_competitions,
    normalize_events,
    normalize_lineups,
    normalize_matches,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — minimal valid StatsBomb-format JSON
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def raw_competitions() -> list[dict]:
    return [
        {
            "competition_id": 11,
            "competition_name": "La Liga",
            "country_name": "Spain",
            "season_id": 90,
            "season_name": "2020/2021",
            "competition_gender": "male",
            "competition_youth": False,
            "competition_international": False,
        },
        {
            "competition_id": 37,
            "competition_name": "FA Women's Super League",
            "country_name": "England",
            "season_id": 42,
            "season_name": "2019/2020",
            "competition_gender": "female",
            "competition_youth": False,
            "competition_international": False,
        },
    ]


@pytest.fixture
def raw_matches() -> list[dict]:
    return [
        {
            "match_id": 3772064,
            "match_date": "2020-09-27",
            "kick_off": "16:00:00.000",
            "match_week": 2,
            "competition": {"competition_id": 11, "competition_name": "La Liga"},
            "season": {"season_id": 90, "season_name": "2020/2021"},
            "home_team": {
                "home_team_id": 217,
                "home_team_name": "Barcelona",
                "home_team_gender": "male",
                "country": {"id": 214, "name": "Spain"},
            },
            "away_team": {
                "away_team_id": 218,
                "away_team_name": "Villarreal",
                "away_team_gender": "male",
                "country": {"id": 214, "name": "Spain"},
            },
            "home_score": 4,
            "away_score": 0,
            "stadium": {"id": 4, "name": "Camp Nou", "country": {"id": 214, "name": "Spain"}},
            "referee": {"id": 123, "name": "Gil Manzano, Juan Martínez"},
            "match_status": "available",
            "metadata": {"data_version": "1.1.0"},
        },
        {
            "match_id": 3772065,
            "match_date": "2020-09-28",
            "kick_off": "20:00:00.000",
            "match_week": 2,
            "competition": {"competition_id": 11, "competition_name": "La Liga"},
            "season": {"season_id": 90, "season_name": "2020/2021"},
            "home_team": {"home_team_id": 220, "home_team_name": "Real Madrid"},
            "away_team": {"away_team_id": 221, "away_team_name": "Getafe"},
            "home_score": 2,
            "away_score": 0,
            "stadium": None,
            "referee": None,
            "match_status": "available",
        },
    ]


@pytest.fixture
def raw_events_pass() -> list[dict]:
    """Events list containing a pass event and a generic event."""
    return [
        {
            "id": "a1b2c3d4-0000-0000-0000-000000000001",
            "index": 1,
            "period": 1,
            "timestamp": "00:00:00.000",
            "minute": 0,
            "second": 0,
            "type": {"id": 35, "name": "Starting XI"},
            "possession": 1,
            "play_pattern": {"id": 1, "name": "Regular Play"},
            "team": {"id": 217, "name": "Barcelona"},
            "duration": 0.0,
            "location": None,
            "under_pressure": None,
        },
        {
            "id": "a1b2c3d4-0000-0000-0000-000000000002",
            "index": 2,
            "period": 1,
            "timestamp": "00:01:14.800",
            "minute": 1,
            "second": 14,
            "type": {"id": 30, "name": "Pass"},
            "possession": 2,
            "play_pattern": {"id": 1, "name": "Regular Play"},
            "team": {"id": 217, "name": "Barcelona"},
            "player": {"id": 5503, "name": "Lionel Andrés Messi Cuccittini"},
            "position": {"id": 17, "name": "Right Wing"},
            "location": [61.0, 40.5],
            "duration": 0.0,
            "under_pressure": False,
            "pass": {
                "recipient": {"id": 6832, "name": "Sergio Busquets i Burgos"},
                "length": 15.3,
                "angle": -0.52,
                "height": {"id": 1, "name": "Ground Pass"},
                "end_location": [75.0, 35.0],
                "type": {"id": 65, "name": "Recovery"},
                "outcome": None,   # successful pass — no outcome key
                "switch": False,
                "through_ball": False,
                "shot_assist": False,
                "goal_assist": False,
                "cross": False,
            },
        },
    ]


@pytest.fixture
def raw_events_shot() -> list[dict]:
    """Events list containing one shot event."""
    return [
        {
            "id": "shot-0000-0000-0000-000000000001",
            "index": 5,
            "period": 1,
            "timestamp": "00:23:45.000",
            "minute": 23,
            "second": 45,
            "type": {"id": 16, "name": "Shot"},
            "possession": 30,
            "play_pattern": {"id": 4, "name": "From Throw In"},
            "team": {"id": 217, "name": "Barcelona"},
            "player": {"id": 5503, "name": "Lionel Andrés Messi Cuccittini"},
            "position": {"id": 17, "name": "Right Wing"},
            "location": [112.0, 38.2],
            "duration": 0.0,
            "under_pressure": True,
            "shot": {
                "statsbomb_xg": 0.23,
                "end_location": [119.0, 36.0, 0.5],
                "outcome": {"id": 58, "name": "Goal"},
                "type": {"id": 87, "name": "Open Play"},
                "technique": {"id": 93, "name": "Normal"},
                "body_part": {"id": 37, "name": "Head"},
                "first_time": False,
                "one_on_one": False,
            },
        }
    ]


@pytest.fixture
def raw_lineups() -> list[dict]:
    return [
        {
            "team_id": 217,
            "team_name": "Barcelona",
            "lineup": [
                {
                    "player_id": 5503,
                    "player_name": "Lionel Andrés Messi Cuccittini",
                    "player_nickname": "Messi",
                    "birth_date": "1987-06-24",
                    "player_height": 170.0,
                    "player_weight": 72.0,
                    "jersey_number": 10,
                    "country": {"id": 11, "name": "Argentina"},
                    "cards": [],
                    "positions": [
                        {
                            "position": "Right Wing",
                            "position_id": 17,
                            "from": "00:00:00.000",
                            "from_period": 1,
                            "to": None,
                            "to_period": None,
                            "start_reason": "Starting XI",
                            "end_reason": None,
                        }
                    ],
                },
                {
                    "player_id": 6832,
                    "player_name": "Sergio Busquets i Burgos",
                    "player_nickname": "Busquets",
                    "birth_date": "1988-07-16",
                    "player_height": 189.0,
                    "player_weight": 76.0,
                    "jersey_number": 5,
                    "country": {"id": 214, "name": "Spain"},
                    "cards": [],
                    "positions": [
                        {
                            "position": "Center Midfield",
                            "position_id": 13,
                            "from": "00:00:00.000",
                            "from_period": 1,
                            "to": None,
                            "to_period": None,
                            "start_reason": "Starting XI",
                            "end_reason": None,
                        }
                    ],
                },
            ],
        },
        {
            "team_id": 218,
            "team_name": "Villarreal",
            "lineup": [
                {
                    "player_id": 9001,
                    "player_name": "Gerard Moreno",
                    "player_nickname": None,
                    "birth_date": "1992-04-07",
                    "player_height": 178.0,
                    "player_weight": 73.0,
                    "jersey_number": 7,
                    "country": {"id": 214, "name": "Spain"},
                    "cards": [],
                    "positions": [
                        {
                            "position": "Center Forward",
                            "position_id": 21,
                            "from": "00:00:00.000",
                            "from_period": 1,
                            "to": None,
                            "to_period": None,
                            "start_reason": "Starting XI",
                            "end_reason": None,
                        }
                    ],
                }
            ],
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tests — _get helper
# ─────────────────────────────────────────────────────────────────────────────


class TestGetHelper:
    def test_single_key(self) -> None:
        assert _get({"a": 1}, "a") == 1

    def test_nested_keys(self) -> None:
        d = {"type": {"id": 30, "name": "Pass"}}
        assert _get(d, "type", "name") == "Pass"
        assert _get(d, "type", "id") == 30

    def test_missing_key_returns_default(self) -> None:
        assert _get({"a": 1}, "b") is None
        assert _get({"a": 1}, "b", default=42) == 42

    def test_none_object_returns_default(self) -> None:
        assert _get(None, "a", "b") is None

    def test_missing_intermediate_key(self) -> None:
        d = {"type": {"id": 30}}
        assert _get(d, "type", "name") is None

    def test_explicit_none_value_returns_default(self) -> None:
        d = {"referee": None}
        assert _get(d, "referee", "name") is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests — normalize_competitions
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeCompetitions:
    def test_returns_dataframe(self, raw_competitions: list[dict]) -> None:
        df = normalize_competitions(raw_competitions)
        assert isinstance(df, pd.DataFrame)

    def test_row_count(self, raw_competitions: list[dict]) -> None:
        df = normalize_competitions(raw_competitions)
        assert len(df) == 2

    def test_required_columns_present(self, raw_competitions: list[dict]) -> None:
        df = normalize_competitions(raw_competitions)
        required = {"competition_id", "competition_name", "country_name",
                    "season_id", "season_name", "competition_gender"}
        assert required.issubset(df.columns)

    def test_competition_id_is_nullable_int(self, raw_competitions: list[dict]) -> None:
        df = normalize_competitions(raw_competitions)
        assert df["competition_id"].dtype == pd.Int64Dtype()

    def test_season_id_is_nullable_int(self, raw_competitions: list[dict]) -> None:
        df = normalize_competitions(raw_competitions)
        assert df["season_id"].dtype == pd.Int64Dtype()

    def test_values_are_correct(self, raw_competitions: list[dict]) -> None:
        df = normalize_competitions(raw_competitions)
        la_liga = df[df["competition_id"] == 11].iloc[0]
        assert la_liga["competition_name"] == "La Liga"
        assert la_liga["country_name"] == "Spain"
        assert la_liga["competition_gender"] == "male"

    def test_empty_input_returns_empty_dataframe(self) -> None:
        df = normalize_competitions([])
        assert df.empty

    def test_output_is_sorted(self, raw_competitions: list[dict]) -> None:
        """Result should be sorted by competition_name."""
        df = normalize_competitions(raw_competitions)
        names = df["competition_name"].tolist()
        assert names == sorted(names)


# ─────────────────────────────────────────────────────────────────────────────
# Tests — normalize_matches
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeMatches:
    def test_row_count(self, raw_matches: list[dict]) -> None:
        df = normalize_matches(raw_matches)
        assert len(df) == 2

    def test_required_columns_present(self, raw_matches: list[dict]) -> None:
        df = normalize_matches(raw_matches)
        required = {
            "match_id", "match_date", "competition_id", "season_id",
            "home_team_id", "home_team_name", "away_team_id", "away_team_name",
            "home_score", "away_score",
        }
        assert required.issubset(df.columns)

    def test_nested_team_is_flattened(self, raw_matches: list[dict]) -> None:
        df = normalize_matches(raw_matches)
        row = df[df["match_id"] == 3772064].iloc[0]
        assert row["home_team_name"] == "Barcelona"
        assert row["away_team_name"] == "Villarreal"
        assert int(row["home_team_id"]) == 217

    def test_score_is_correct(self, raw_matches: list[dict]) -> None:
        df = normalize_matches(raw_matches)
        row = df[df["match_id"] == 3772064].iloc[0]
        assert int(row["home_score"]) == 4
        assert int(row["away_score"]) == 0

    def test_stadium_extracted(self, raw_matches: list[dict]) -> None:
        df = normalize_matches(raw_matches)
        row = df[df["match_id"] == 3772064].iloc[0]
        assert row["stadium_name"] == "Camp Nou"

    def test_none_stadium_is_null(self, raw_matches: list[dict]) -> None:
        """Match without a stadium should have null stadium_name."""
        df = normalize_matches(raw_matches)
        row = df[df["match_id"] == 3772065].iloc[0]
        assert row["stadium_name"] is None or (isinstance(row["stadium_name"], float) and math.isnan(row["stadium_name"]))

    def test_match_date_is_python_date(self, raw_matches: list[dict]) -> None:
        import datetime
        df = normalize_matches(raw_matches)
        row = df[df["match_id"] == 3772064].iloc[0]
        assert isinstance(row["match_date"], datetime.date)

    def test_id_columns_are_nullable_int(self, raw_matches: list[dict]) -> None:
        df = normalize_matches(raw_matches)
        for col in ["match_id", "competition_id", "season_id", "home_team_id", "away_team_id"]:
            assert df[col].dtype == pd.Int64Dtype(), f"Column {col!r} should be Int64"

    def test_empty_input_returns_empty_dataframe(self) -> None:
        df = normalize_matches([])
        assert df.empty


# ─────────────────────────────────────────────────────────────────────────────
# Tests — normalize_events
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeEvents:
    MATCH_ID = 3772064

    def test_row_count(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        assert len(df) == 2

    def test_match_id_injected(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        assert (df["match_id"] == self.MATCH_ID).all()

    def test_core_columns_present(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        required = {
            "event_id", "match_id", "index", "period", "minute", "second",
            "type_id", "type_name", "team_id", "team_name",
            "location_x", "location_y", "under_pressure",
        }
        assert required.issubset(df.columns)

    def test_pass_columns_present(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        pass_cols = {"pass_length", "pass_angle", "pass_end_x", "pass_end_y",
                     "pass_recipient_id", "pass_outcome", "pass_cross"}
        assert pass_cols.issubset(df.columns)

    def test_shot_columns_present(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        shot_cols = {"shot_statsbomb_xg", "shot_outcome", "shot_end_x", "shot_end_y"}
        assert shot_cols.issubset(df.columns)

    def test_pass_event_has_correct_values(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        pass_row = df[df["type_name"] == "Pass"].iloc[0]
        assert pass_row["player_name"] == "Lionel Andrés Messi Cuccittini"
        assert abs(float(pass_row["pass_length"]) - 15.3) < 0.01
        assert float(pass_row["location_x"]) == pytest.approx(61.0, abs=0.1)
        assert float(pass_row["location_y"]) == pytest.approx(40.5, abs=0.1)
        assert float(pass_row["pass_end_x"]) == pytest.approx(75.0, abs=0.1)

    def test_non_pass_event_has_null_pass_columns(self, raw_events_pass: list[dict]) -> None:
        """Starting XI event must have null pass columns — not carry-over from previous row."""
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        xi_row = df[df["type_name"] == "Starting XI"].iloc[0]
        val = xi_row["pass_length"]
        # numpy float32 NaN satisfies math.isnan(); None also acceptable
        assert val is None or math.isnan(float(val))

    def test_shot_event_xg(self, raw_events_shot: list[dict]) -> None:
        df = normalize_events(raw_events_shot, self.MATCH_ID)
        shot_row = df[df["type_name"] == "Shot"].iloc[0]
        assert float(shot_row["shot_statsbomb_xg"]) == pytest.approx(0.23, abs=0.001)
        assert shot_row["shot_outcome"] == "Goal"

    def test_shot_end_location_includes_z(self, raw_events_shot: list[dict]) -> None:
        df = normalize_events(raw_events_shot, self.MATCH_ID)
        shot_row = df[df["type_name"] == "Shot"].iloc[0]
        assert float(shot_row["shot_end_z"]) == pytest.approx(0.5, abs=0.01)

    def test_under_pressure_is_bool(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        assert df["under_pressure"].dtype == bool

    def test_under_pressure_none_becomes_false(self, raw_events_pass: list[dict]) -> None:
        """Null under_pressure in source should normalize to False."""
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        xi_row = df[df["type_name"] == "Starting XI"].iloc[0]
        # numpy.False_ == False is True; use bool() to ensure Python bool comparison
        assert bool(xi_row["under_pressure"]) is False

    def test_minute_is_nullable_int(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        assert df["minute"].dtype == pd.Int64Dtype()

    def test_location_is_float32(self, raw_events_pass: list[dict]) -> None:
        df = normalize_events(raw_events_pass, self.MATCH_ID)
        assert df["location_x"].dtype == "float32"
        assert df["location_y"].dtype == "float32"

    def test_empty_input_returns_empty_dataframe(self) -> None:
        df = normalize_events([], self.MATCH_ID)
        assert df.empty


# ─────────────────────────────────────────────────────────────────────────────
# Tests — normalize_lineups
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeLineups:
    MATCH_ID = 3772064

    def test_row_count(self, raw_lineups: list[dict]) -> None:
        df = normalize_lineups(raw_lineups, self.MATCH_ID)
        # 2 Barcelona players + 1 Villarreal player
        assert len(df) == 3

    def test_match_id_injected(self, raw_lineups: list[dict]) -> None:
        df = normalize_lineups(raw_lineups, self.MATCH_ID)
        assert (df["match_id"] == self.MATCH_ID).all()

    def test_required_columns_present(self, raw_lineups: list[dict]) -> None:
        df = normalize_lineups(raw_lineups, self.MATCH_ID)
        required = {
            "match_id", "team_id", "team_name",
            "player_id", "player_name", "jersey_number",
            "height_cm", "weight_kg", "country_name",
            "starting_position", "starting_position_id",
        }
        assert required.issubset(df.columns)

    def test_messi_row_is_correct(self, raw_lineups: list[dict]) -> None:
        df = normalize_lineups(raw_lineups, self.MATCH_ID)
        messi = df[df["player_id"] == 5503].iloc[0]
        assert messi["player_name"] == "Lionel Andrés Messi Cuccittini"
        assert messi["player_nickname"] == "Messi"
        assert int(messi["jersey_number"]) == 10
        assert float(messi["height_cm"]) == pytest.approx(170.0, abs=0.1)
        assert messi["country_name"] == "Argentina"
        assert messi["starting_position"] == "Right Wing"
        assert int(messi["starting_position_id"]) == 17

    def test_both_teams_included(self, raw_lineups: list[dict]) -> None:
        df = normalize_lineups(raw_lineups, self.MATCH_ID)
        team_ids = set(df["team_id"].astype(int).tolist())
        assert 217 in team_ids  # Barcelona
        assert 218 in team_ids  # Villarreal

    def test_id_columns_are_nullable_int(self, raw_lineups: list[dict]) -> None:
        df = normalize_lineups(raw_lineups, self.MATCH_ID)
        for col in ["player_id", "team_id", "jersey_number", "country_id", "starting_position_id"]:
            assert df[col].dtype == pd.Int64Dtype(), f"Column {col!r} should be Int64"

    def test_height_is_float32(self, raw_lineups: list[dict]) -> None:
        df = normalize_lineups(raw_lineups, self.MATCH_ID)
        assert df["height_cm"].dtype == "float32"
        assert df["weight_kg"].dtype == "float32"

    def test_empty_input_returns_empty_dataframe(self) -> None:
        df = normalize_lineups([], self.MATCH_ID)
        assert df.empty

    def test_player_with_no_positions_has_null_starting_position(self) -> None:
        """A substitute who never started has null starting_position."""
        data = [
            {
                "team_id": 217,
                "team_name": "Barcelona",
                "lineup": [
                    {
                        "player_id": 9999,
                        "player_name": "Sub Player",
                        "player_nickname": None,
                        "birth_date": None,
                        "player_height": None,
                        "player_weight": None,
                        "jersey_number": 20,
                        "country": {"id": 214, "name": "Spain"},
                        "cards": [],
                        "positions": [],  # No positions — came on from bench
                    }
                ],
            }
        ]
        df = normalize_lineups(data, 9999)
        assert df.iloc[0]["starting_position"] is None
