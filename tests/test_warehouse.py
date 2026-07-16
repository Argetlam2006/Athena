"""
tests/test_warehouse.py — Warehouse and analytical SQL view tests

All tests use in-memory DuckDB (":memory:") via the Warehouse(_conn=)
injection parameter — no filesystem access, no Parquet files required.

Test coverage:
  - Warehouse initialisation and Parquet registration
  - All five analytical SQL views exist and return correct schemas
  - vw_player_summary correctness (aggregation, per-90, ratios)
  - vw_team_summary correctness (W/D/L points, xG, UNION ALL)
  - vw_match_summary correctness (result classification, xG differential)
  - vw_player_percentiles correctness (PERCENT_RANK bounds, NTILE range)
  - vw_recruitment_candidates correctness (score range, ROW_NUMBER)
  - WarehouseQueries filter parameters
  - list_views() introspection
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from backend.warehouse.queries import WarehouseQueries
from backend.warehouse.warehouse import SQL_VIEWS_DIR, Warehouse

# ─────────────────────────────────────────────────────────────────────────────
# Synthetic test dataset
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def sample_competitions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "competition_id": 11,
                "competition_name": "La Liga",
                "country_name": "Spain",
                "season_id": 90,
                "season_name": "2020/2021",
                "competition_gender": "male",
            },
        ]
    )


@pytest.fixture(scope="module")
def sample_matches() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": 3001,
                "match_date": "2020-09-27",
                "kick_off": "16:00:00",
                "match_week": 1,
                "competition_id": 11,
                "competition_name": "La Liga",
                "season_id": 90,
                "season_name": "2020/2021",
                "home_team_id": 101,
                "home_team_name": "Barcelona",
                "away_team_id": 102,
                "away_team_name": "Villarreal",
                "home_score": 4,
                "away_score": 0,
                "stadium_name": "Camp Nou",
                "referee_name": "Gil Manzano",
                "match_status": "available",
            },
            {
                "match_id": 3002,
                "match_date": "2020-10-04",
                "kick_off": "20:00:00",
                "match_week": 2,
                "competition_id": 11,
                "competition_name": "La Liga",
                "season_id": 90,
                "season_name": "2020/2021",
                "home_team_id": 102,
                "home_team_name": "Villarreal",
                "away_team_id": 101,
                "away_team_name": "Barcelona",
                "home_score": 1,
                "away_score": 2,
                "stadium_name": "La Ceramica",
                "referee_name": None,
                "match_status": "available",
            },
        ]
    )


@pytest.fixture(scope="module")
def sample_lineups() -> pd.DataFrame:
    """Three players: Messi + Busquets for Barcelona, Moreno for Villarreal."""
    rows = []
    # Messi — both matches for Barcelona
    for match_id in [3001, 3002]:
        rows.append(
            {
                "match_id": match_id,
                "team_id": 101,
                "team_name": "Barcelona",
                "player_id": 5503,
                "player_name": "Lionel Messi",
                "player_nickname": "Messi",
                "jersey_number": 10,
                "birth_date": "1987-06-24",
                "height_cm": 170.0,
                "weight_kg": 72.0,
                "country_id": 11,
                "country_name": "Argentina",
                "starting_position": "Right Wing",
                "starting_position_id": 17,
            }
        )
    # Busquets — both matches for Barcelona
    for match_id in [3001, 3002]:
        rows.append(
            {
                "match_id": match_id,
                "team_id": 101,
                "team_name": "Barcelona",
                "player_id": 6832,
                "player_name": "Sergio Busquets",
                "player_nickname": "Busquets",
                "jersey_number": 5,
                "birth_date": "1988-07-16",
                "height_cm": 189.0,
                "weight_kg": 76.0,
                "country_id": 214,
                "country_name": "Spain",
                "starting_position": "Center Midfield",
                "starting_position_id": 13,
            }
        )
    # Moreno — both matches for Villarreal
    for match_id in [3001, 3002]:
        rows.append(
            {
                "match_id": match_id,
                "team_id": 102,
                "team_name": "Villarreal",
                "player_id": 9001,
                "player_name": "Gerard Moreno",
                "player_nickname": None,
                "jersey_number": 7,
                "birth_date": "1992-04-07",
                "height_cm": 178.0,
                "weight_kg": 73.0,
                "country_id": 214,
                "country_name": "Spain",
                "starting_position": "Center Forward",
                "starting_position_id": 21,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def sample_events() -> pd.DataFrame:
    """
    Minimal synthetic events covering Pass, Shot, Carry, Dribble for
    two players across two matches.

    Messi:   2 goals, 3 shots (xG 0.3, 0.2, 0.1), 10 passes (8 accurate),
             5 carries (progressive), 3 dribbles (2 complete)
    Busquets: 0 goals, 20 passes (18 accurate), 0 shots
    Moreno:  1 goal, 2 shots (xG 0.25, 0.15), 8 passes (7 accurate)
    All events are for match 3001 only for simplicity.
    """
    rows = []
    eid = 1

    def ev(match_id, player_id, player_name, team_id, team_name, type_name, **kwargs):
        nonlocal eid
        base = {
            "event_id": f"evt-{eid:04d}",
            "match_id": match_id,
            "index": eid,
            "period": 1,
            "timestamp": "00:10:00.000",
            "minute": 10,
            "second": 0,
            "type_id": 30,
            "type_name": type_name,
            "play_pattern": "Regular Play",
            "possession": eid,
            "team_id": team_id,
            "team_name": team_name,
            "player_id": player_id,
            "player_name": player_name,
            "position_name": "Right Wing",
            "location_x": 60.0,
            "location_y": 40.0,
            "duration": 0.0,
            "under_pressure": False,
            # Pass nulls
            "pass_length": None,
            "pass_angle": None,
            "pass_end_x": None,
            "pass_end_y": None,
            "pass_recipient_id": None,
            "pass_recipient_name": None,
            "pass_height": None,
            "pass_type": None,
            "pass_outcome": None,
            "pass_switch": False,
            "pass_through_ball": False,
            "pass_shot_assist": False,
            "pass_goal_assist": False,
            "pass_cross": False,
            # Shot nulls
            "shot_statsbomb_xg": None,
            "shot_end_x": None,
            "shot_end_y": None,
            "shot_end_z": None,
            "shot_outcome": None,
            "shot_type": None,
            "shot_technique": None,
            "shot_body_part": None,
            "shot_first_time": False,
            "shot_one_on_one": False,
            # Carry nulls
            "carry_end_x": None,
            "carry_end_y": None,
            # Dribble nulls
            "dribble_outcome": None,
            "dribble_overrun": False,
            "dribble_nutmeg": False,
        }
        base.update(kwargs)
        eid += 1
        return base

    # ── Messi: shots ──────────────────────────────────────────────────────────
    rows.append(
        ev(
            3001,
            5503,
            "Lionel Messi",
            101,
            "Barcelona",
            "Shot",
            shot_statsbomb_xg=0.30,
            shot_outcome="Goal",
            shot_type="Open Play",
            location_x=110.0,
            location_y=38.0,
        )
    )
    rows.append(
        ev(
            3001,
            5503,
            "Lionel Messi",
            101,
            "Barcelona",
            "Shot",
            shot_statsbomb_xg=0.20,
            shot_outcome="Goal",
            shot_type="Open Play",
            location_x=108.0,
            location_y=36.0,
        )
    )
    rows.append(
        ev(
            3001,
            5503,
            "Lionel Messi",
            101,
            "Barcelona",
            "Shot",
            shot_statsbomb_xg=0.10,
            shot_outcome="Saved",
            shot_type="Open Play",
            location_x=105.0,
            location_y=40.0,
        )
    )
    # Messi: second match shots
    rows.append(
        ev(
            3002,
            5503,
            "Lionel Messi",
            101,
            "Barcelona",
            "Shot",
            shot_statsbomb_xg=0.15,
            shot_outcome="Goal",
            shot_type="Open Play",
            location_x=112.0,
            location_y=35.0,
        )
    )

    # ── Messi: passes ─────────────────────────────────────────────────────────
    for i in range(8):  # 8 accurate passes
        rows.append(
            ev(
                3001,
                5503,
                "Lionel Messi",
                101,
                "Barcelona",
                "Pass",
                pass_length=15.0 + i,
                pass_angle=0.5,
                pass_end_x=75.0,
                pass_end_y=35.0,
                pass_outcome=None,
            )
        )  # None = successful
    for _ in range(2):  # 2 inaccurate passes
        rows.append(
            ev(
                3001,
                5503,
                "Lionel Messi",
                101,
                "Barcelona",
                "Pass",
                pass_length=30.0,
                pass_angle=1.0,
                pass_end_x=90.0,
                pass_end_y=20.0,
                pass_outcome="Incomplete",
            )
        )

    # ── Messi: carries ────────────────────────────────────────────────────────
    for i in range(5):
        rows.append(
            ev(
                3001,
                5503,
                "Lionel Messi",
                101,
                "Barcelona",
                "Carry",
                location_x=60.0,
                location_y=40.0,
                carry_end_x=72.0 + i,
                carry_end_y=38.0,
            )
        )  # progressive

    # ── Messi: dribbles ───────────────────────────────────────────────────────
    rows.append(
        ev(
            3001,
            5503,
            "Lionel Messi",
            101,
            "Barcelona",
            "Dribble",
            dribble_outcome="Complete",
        )
    )
    rows.append(
        ev(
            3001,
            5503,
            "Lionel Messi",
            101,
            "Barcelona",
            "Dribble",
            dribble_outcome="Complete",
        )
    )
    rows.append(
        ev(
            3001,
            5503,
            "Lionel Messi",
            101,
            "Barcelona",
            "Dribble",
            dribble_outcome="Incomplete",
        )
    )

    # ── Busquets: passes ──────────────────────────────────────────────────────
    for _ in range(18):  # 18 accurate
        rows.append(
            ev(
                3001,
                6832,
                "Sergio Busquets",
                101,
                "Barcelona",
                "Pass",
                pass_length=12.0,
                pass_angle=0.2,
                pass_end_x=65.0,
                pass_end_y=40.0,
                pass_outcome=None,
            )
        )
    for _ in range(2):  # 2 inaccurate
        rows.append(
            ev(
                3001,
                6832,
                "Sergio Busquets",
                101,
                "Barcelona",
                "Pass",
                pass_length=20.0,
                pass_angle=0.8,
                pass_end_x=80.0,
                pass_end_y=30.0,
                pass_outcome="Out",
            )
        )
    # Busquets second match — 15 accurate passes
    for _ in range(15):
        rows.append(
            ev(
                3002,
                6832,
                "Sergio Busquets",
                101,
                "Barcelona",
                "Pass",
                pass_length=11.0,
                pass_angle=0.3,
                pass_end_x=63.0,
                pass_end_y=41.0,
                pass_outcome=None,
            )
        )

    # ── Moreno: shots ─────────────────────────────────────────────────────────
    rows.append(
        ev(
            3001,
            9001,
            "Gerard Moreno",
            102,
            "Villarreal",
            "Shot",
            shot_statsbomb_xg=0.25,
            shot_outcome="Saved",
            shot_type="Open Play",
            location_x=109.0,
            location_y=36.0,
        )
    )
    rows.append(
        ev(
            3001,
            9001,
            "Gerard Moreno",
            102,
            "Villarreal",
            "Shot",
            shot_statsbomb_xg=0.15,
            shot_outcome="Blocked",
            shot_type="Open Play",
            location_x=107.0,
            location_y=34.0,
        )
    )

    # ── Moreno: passes ────────────────────────────────────────────────────────
    for _ in range(7):
        rows.append(
            ev(
                3001,
                9001,
                "Gerard Moreno",
                102,
                "Villarreal",
                "Pass",
                pass_length=10.0,
                pass_angle=0.4,
                pass_end_x=70.0,
                pass_end_y=38.0,
                pass_outcome=None,
            )
        )
    rows.append(
        ev(
            3001,
            9001,
            "Gerard Moreno",
            102,
            "Villarreal",
            "Pass",
            pass_length=25.0,
            pass_angle=1.2,
            pass_end_x=85.0,
            pass_end_y=25.0,
            pass_outcome="Incomplete",
        )
    )

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Warehouse fixture — in-memory DuckDB, tables registered from DataFrames
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def wh_conn(
    sample_competitions,
    sample_matches,
    sample_lineups,
    sample_events,
) -> duckdb.DuckDBPyConnection:
    """
    Return an in-memory DuckDB connection with base tables and all five
    analytical views created. Shared across all tests in this module.
    """
    conn = duckdb.connect(":memory:")

    # Register DataFrames as DuckDB views (same as reading from Parquet)
    conn.register("competitions", sample_competitions)
    conn.register("matches", sample_matches)
    conn.register("lineups", sample_lineups)
    conn.register("events", sample_events)

    # Use Warehouse to create all analytical SQL views
    wh = Warehouse(_conn=conn)
    wh._create_views(conn)

    return conn


@pytest.fixture
def q(wh_conn) -> WarehouseQueries:
    """WarehouseQueries bound to the shared in-memory connection."""
    return WarehouseQueries(wh_conn)


# ─────────────────────────────────────────────────────────────────────────────
# Tests — Warehouse initialisation
# ─────────────────────────────────────────────────────────────────────────────


class TestWarehouseInit:
    def test_sql_views_directory_exists(self) -> None:
        assert SQL_VIEWS_DIR.exists(), f"sql/views/ not found at {SQL_VIEWS_DIR}"

    def test_sql_views_directory_has_five_files(self) -> None:
        sql_files = sorted(SQL_VIEWS_DIR.glob("*.sql"))
        assert len(sql_files) == 5, f"Expected 5 SQL files, found {len(sql_files)}"

    def test_sql_files_have_numbered_prefixes(self) -> None:
        files = [f.name for f in sorted(SQL_VIEWS_DIR.glob("*.sql"))]
        for i, fname in enumerate(files, start=1):
            assert fname.startswith(f"0{i}_"), f"File {fname} should start with 0{i}_"

    def test_all_views_created(self, wh_conn) -> None:
        q = WarehouseQueries(wh_conn)
        views = q.list_views()
        expected = {
            "vw_match_summary",
            "vw_player_summary",
            "vw_team_summary",
            "vw_player_percentiles",
            "vw_recruitment_candidates",
        }
        missing = expected - set(views)
        assert not missing, f"Missing views: {missing}"

    def test_warehouse_build_with_injected_conn(self, wh_conn) -> None:
        """Warehouse._setup() should be idempotent — calling twice is safe."""
        wh = Warehouse(_conn=wh_conn)
        wh._create_views(wh_conn)  # second call — CREATE OR REPLACE should not raise
        q = WarehouseQueries(wh_conn)
        assert "vw_player_summary" in q.list_views()


# ─────────────────────────────────────────────────────────────────────────────
# Tests — vw_match_summary
# ─────────────────────────────────────────────────────────────────────────────


class TestMatchSummaryView:
    def test_returns_two_rows(self, q) -> None:
        df = q.get_match_summary()
        assert len(df) == 2

    def test_required_columns_present(self, q) -> None:
        df = q.get_match_summary()
        required = {
            "match_id",
            "competition_name",
            "home_team_name",
            "away_team_name",
            "home_score",
            "away_score",
            "result",
            "total_goals",
            "match_classification",
            "xg_differential",
            "home_shot_share_pct",
        }
        assert required.issubset(df.columns)

    def test_result_classification_home_win(self, q) -> None:
        df = q.get_match_summary()
        match_1 = df[df["match_id"] == 3001].iloc[0]
        assert match_1["result"] == "Home Win"
        assert int(match_1["total_goals"]) == 4

    def test_result_classification_away_win(self, q) -> None:
        df = q.get_match_summary()
        match_2 = df[df["match_id"] == 3002].iloc[0]
        assert match_2["result"] == "Away Win"

    def test_match_classification_high_scoring(self, q) -> None:
        df = q.get_match_summary()
        match_1 = df[df["match_id"] == 3001].iloc[0]
        assert match_1["match_classification"] == "High Scoring"

    def test_xg_differential_is_numeric(self, q) -> None:
        df = q.get_match_summary()
        assert df["xg_differential"].dtype.kind in ("f", "i", "u")

    def test_competition_filter(self, q) -> None:
        df = q.get_match_summary(competition="La Liga")
        assert len(df) == 2

    def test_nonexistent_competition_returns_empty(self, q) -> None:
        df = q.get_match_summary(competition="Premier League")
        assert df.empty

    def test_home_shot_share_between_0_and_100(self, q) -> None:
        df = q.get_match_summary()
        valid = df["home_shot_share_pct"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


# ─────────────────────────────────────────────────────────────────────────────
# Tests — vw_player_summary
# ─────────────────────────────────────────────────────────────────────────────


class TestPlayerSummaryView:
    def test_returns_three_players(self, q) -> None:
        """Three unique players in the test dataset."""
        df = q.get_player_summary()
        assert len(df) == 3

    def test_required_columns_present(self, q) -> None:
        df = q.get_player_summary()
        required = {
            "player_id",
            "player_name",
            "team_name",
            "position_name",
            "matches_played",
            "minutes_played",
            "goals",
            "xg_total",
            "total_passes",
            "pass_accuracy_pct",
            "goals_p90",
            "xg_p90",
        }
        assert required.issubset(df.columns)

    def test_messi_goals_correct(self, q) -> None:
        df = q.get_player_summary()
        messi = df[df["player_id"] == 5503].iloc[0]
        # 3 goals in match 3001, 1 goal in match 3002
        assert int(messi["goals"]) == 3  # Only match 3001 has goals event

    def test_messi_xg_aggregated(self, q) -> None:
        df = q.get_player_summary()
        messi = df[df["player_id"] == 5503].iloc[0]
        expected_xg = 0.30 + 0.20 + 0.10 + 0.15  # all four shots
        assert abs(float(messi["xg_total"]) - expected_xg) < 0.01

    def test_messi_pass_accuracy(self, q) -> None:
        df = q.get_player_summary()
        messi = df[df["player_id"] == 5503].iloc[0]
        # 8 accurate out of 10 total in match 3001 (match 3002 has no passes)
        assert abs(float(messi["pass_accuracy_pct"]) - 80.0) < 1.0

    def test_busquets_has_zero_goals(self, q) -> None:
        df = q.get_player_summary()
        busquets = df[df["player_id"] == 6832].iloc[0]
        assert int(busquets["goals"]) == 0
        assert float(busquets["xg_total"]) == 0.0

    def test_busquets_pass_accuracy_high(self, q) -> None:
        df = q.get_player_summary()
        busquets = df[df["player_id"] == 6832].iloc[0]
        # 33 accurate out of 35 total (matches 3001 + 3002)
        assert float(busquets["pass_accuracy_pct"]) > 90.0

    def test_matches_played_is_correct(self, q) -> None:
        df = q.get_player_summary()
        messi = df[df["player_id"] == 5503].iloc[0]
        assert int(messi["matches_played"]) == 2

    def test_minutes_played_is_reconstructed(self, q) -> None:
        df = q.get_player_summary()
        messi = df[df["player_id"] == 5503].iloc[0]
        # Reconstructed from MAX(minute) in mock events, which is 10 per match (2 matches)
        assert int(messi["minutes_played"]) == 20

    def test_goals_p90_is_calculated(self, q) -> None:
        df = q.get_player_summary()
        messi = df[df["player_id"] == 5503].iloc[0]
        # 3 goals / 20 minutes × 90 = 13.5
        assert abs(float(messi["goals_p90"]) - 13.5) < 0.01

    def test_pass_accuracy_pct_within_0_100(self, q) -> None:
        df = q.get_player_summary()
        assert (df["pass_accuracy_pct"].fillna(0) >= 0).all()
        assert (df["pass_accuracy_pct"].fillna(0) <= 100).all()

    def test_dribble_success_pct_within_bounds(self, q) -> None:
        df = q.get_player_summary()
        messi = df[df["player_id"] == 5503].iloc[0]
        # 2 complete out of 3 dribbles = 66.7%
        assert abs(float(messi["dribble_success_pct"]) - 66.7) < 1.0

    def test_position_filter(self, q) -> None:
        df = q.get_player_summary(position="Center Midfield")
        assert len(df) == 1
        assert df.iloc[0]["player_name"] == "Sergio Busquets"

    def test_team_filter(self, q) -> None:
        df = q.get_player_summary(team="Villarreal")
        assert len(df) == 1
        assert df.iloc[0]["player_id"] == 9001

    def test_min_matches_filter_excludes_one_match_players(self, q) -> None:
        # All players have 2 matches; requesting min_matches=3 returns empty
        df = q.get_player_summary(min_matches=3)
        assert df.empty


# ─────────────────────────────────────────────────────────────────────────────
# Tests — vw_team_summary
# ─────────────────────────────────────────────────────────────────────────────


class TestTeamSummaryView:
    def test_returns_two_teams(self, q) -> None:
        df = q.get_team_summary()
        assert len(df) == 2

    def test_required_columns_present(self, q) -> None:
        df = q.get_team_summary()
        required = {
            "team_id",
            "team_name",
            "matches_played",
            "wins",
            "draws",
            "losses",
            "points",
            "goals_scored",
            "goals_conceded",
            "goal_difference",
            "xg_for",
            "xg_against",
            "xg_difference",
            "pass_accuracy_pct",
        }
        assert required.issubset(df.columns)

    def test_barcelona_wins_and_points(self, q) -> None:
        df = q.get_team_summary()
        barca = df[df["team_id"] == 101].iloc[0]
        # Match 3001: Barcelona wins 4-0 (Home)
        # Match 3002: Barcelona wins 2-1 (Away)
        assert int(barca["wins"]) == 2
        assert int(barca["draws"]) == 0
        assert int(barca["losses"]) == 0
        assert int(barca["points"]) == 6

    def test_villarreal_losses(self, q) -> None:
        df = q.get_team_summary()
        villa = df[df["team_id"] == 102].iloc[0]
        assert int(villa["losses"]) == 2
        assert int(villa["points"]) == 0

    def test_goals_scored_correct(self, q) -> None:
        df = q.get_team_summary()
        barca = df[df["team_id"] == 101].iloc[0]
        # 4 goals (match 3001 home) + 2 goals (match 3002 away)
        assert int(barca["goals_scored"]) == 6

    def test_goal_difference_correct(self, q) -> None:
        df = q.get_team_summary()
        barca = df[df["team_id"] == 101].iloc[0]
        assert int(barca["goal_difference"]) == 5  # scored 6, conceded 1

    def test_xg_for_is_positive(self, q) -> None:
        df = q.get_team_summary()
        assert (df["xg_for"].fillna(0) >= 0).all()


# ─────────────────────────────────────────────────────────────────────────────
# Tests — vw_player_percentiles
# ─────────────────────────────────────────────────────────────────────────────


class TestPlayerPercentilesView:
    def test_returns_rows(self, q) -> None:
        df = q.get_player_percentiles()
        assert not df.empty

    def test_required_columns_present(self, q) -> None:
        df = q.get_player_percentiles()
        required = {
            "player_id",
            "position_name",
            "xg_p90_pct_in_position",
            "goals_p90_pct_in_position",
            "pass_acc_pct_in_position",
            "overall_percentile",
            "xg_decile",
            "xg_p90_decile_in_position",
        }
        assert required.issubset(df.columns)

    def test_percentile_values_in_0_to_100_range(self, q) -> None:
        df = q.get_player_percentiles()
        pct_cols = [
            c
            for c in df.columns
            if c.endswith("_pct_in_position") or c == "overall_percentile"
        ]
        for col in pct_cols:
            vals = df[col].dropna()
            assert (vals >= 0).all() and (vals <= 100).all(), (
                f"Column {col!r} has values outside [0, 100]"
            )

    def test_ntile_decile_in_1_to_10_range(self, q) -> None:
        df = q.get_player_percentiles()
        decile_vals = df["xg_decile"].dropna()
        assert (decile_vals >= 1).all() and (decile_vals <= 10).all()

    def test_overall_percentile_is_numeric(self, q) -> None:
        df = q.get_player_percentiles()
        assert df["overall_percentile"].dtype.kind in ("f", "i", "u")

    def test_position_filter(self, q) -> None:
        df = q.get_player_percentiles(position="Right Wing")
        assert len(df) == 1
        assert df.iloc[0]["player_id"] == 5503


# ─────────────────────────────────────────────────────────────────────────────
# Tests — vw_recruitment_candidates
# ─────────────────────────────────────────────────────────────────────────────


class TestRecruitmentCandidatesView:
    def test_returns_rows(self, q) -> None:
        # min_matches=2 by default in get_recruitment_candidates
        df = q.get_recruitment_candidates(min_matches=2)
        assert not df.empty

    def test_required_columns_present(self, q) -> None:
        df = q.get_recruitment_candidates(min_matches=2)
        required = {
            "player_id",
            "player_name",
            "position_name",
            "team_name",
            "contribution_score",
            "position_rank",
            "position_pool_size",
            "is_clinical_finisher",
            "is_high_volume_passer",
            "is_progressive_passer",
            "is_elite_dribbler",
        }
        assert required.issubset(df.columns)

    def test_contribution_score_in_0_to_100(self, q) -> None:
        df = q.get_recruitment_candidates(min_matches=2)
        scores = df["contribution_score"].dropna()
        assert (scores >= 0).all() and (scores <= 100).all()

    def test_position_rank_starts_at_1(self, q) -> None:
        df = q.get_recruitment_candidates(min_matches=2)
        for pos in df["position_name"].dropna().unique():
            group = df[df["position_name"] == pos]
            assert int(group["position_rank"].min()) == 1

    def test_top_n_parameter(self, q) -> None:
        df = q.get_recruitment_candidates(min_matches=2, top_n=1)
        assert len(df) == 1

    def test_position_filter(self, q) -> None:
        df = q.get_recruitment_candidates(position="Center Midfield", min_matches=2)
        if not df.empty:
            assert (df["position_name"] == "Center Midfield").all()


# ─────────────────────────────────────────────────────────────────────────────
# Tests — WarehouseQueries utility methods
# ─────────────────────────────────────────────────────────────────────────────


class TestWarehouseQueries:
    def test_list_views_returns_all_five(self, q) -> None:
        views = q.list_views()
        expected = {
            "vw_match_summary",
            "vw_player_summary",
            "vw_team_summary",
            "vw_player_percentiles",
            "vw_recruitment_candidates",
        }
        assert expected.issubset(set(views))

    def test_get_player_by_id(self, q) -> None:
        df = q.get_player_by_id(5503)
        assert len(df) == 1
        assert df.iloc[0]["player_name"] == "Lionel Messi"

    def test_execute_escape_hatch(self, q) -> None:
        df = q.execute("SELECT COUNT(*) AS n FROM vw_player_summary")
        assert df.iloc[0]["n"] == 3
