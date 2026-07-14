"""
backend/warehouse/queries.py — Typed Python interface over analytical SQL views

WarehouseQueries encapsulates every SQL SELECT that downstream code needs.
No module outside this file should ever construct a raw SQL string.

Each method:
  - Accepts optional filter parameters (competition, season, position, etc.)
  - Returns a typed pandas DataFrame
  - Uses DuckDB parameter binding to prevent injection
  - Has a clear docstring explaining what the view returns

Usage:
    from backend.warehouse.connection import connect
    from backend.warehouse.queries import WarehouseQueries

    with connect() as conn:
        q = WarehouseQueries(conn)
        df = q.get_player_summary(competition="La Liga")
        df = q.get_player_percentiles(position="Center Forward", min_matches=3)
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd


@dataclass
class WarehouseQueries:
    """
    Query interface for the Athena Analytics Warehouse.

    All methods take an open DuckDB connection and return DataFrames.
    Accepts optional filter parameters — omit to query all available data.

    Filters use DuckDB parameterized queries (? placeholders) to avoid
    string injection even in internal analytical code.
    """

    conn: duckdb.DuckDBPyConnection

    # ─────────────────────────────────────────────────────────────────────────
    # Match queries
    # ─────────────────────────────────────────────────────────────────────────

    def get_match_summary(
        self,
        competition: str | None = None,
        season: str | None = None,
    ) -> pd.DataFrame:
        """
        Return match-level analytical overview from vw_match_summary.

        Includes: teams, score, result, xG per team, pass accuracy,
        shot counts, and derived match character (High Scoring / Normal / Goalless).

        Args:
            competition: Filter by competition name (e.g. "La Liga").
            season:      Filter by season name (e.g. "2020/2021").

        Returns:
            DataFrame with one row per match, ordered by match_date DESC.
        """
        conditions, params = ["1=1"], []
        if competition:
            conditions.append("competition_name = ?")
            params.append(competition)
        if season:
            conditions.append("season_name = ?")
            params.append(season)

        sql = f"""
            SELECT *
            FROM   vw_match_summary
            WHERE  {" AND ".join(conditions)}
            ORDER  BY match_date DESC, match_id
        """
        return self.conn.execute(sql, params).df()

    # ─────────────────────────────────────────────────────────────────────────
    # Player queries
    # ─────────────────────────────────────────────────────────────────────────

    def get_player_summary(
        self,
        competition: str | None = None,
        season: str | None = None,
        position: str | None = None,
        team: str | None = None,
        min_matches: int = 1,
    ) -> pd.DataFrame:
        """
        Return aggregated player statistics from vw_player_summary.

        Each row is one player in one competition-season with their full
        performance profile: goals, xG, passes, carries, dribbles, per-90
        metrics, and quality ratios.

        Args:
            competition:  Filter by competition name.
            season:       Filter by season name.
            position:     Filter by primary position (e.g. "Right Wing").
            team:         Filter by team name.
            min_matches:  Minimum matches played (default: 1).

        Returns:
            DataFrame ordered by xg_total DESC, goals DESC.
        """
        conditions = [f"matches_played >= {min_matches}"]
        params: list = []

        if competition:
            conditions.append("competition_name = ?")
            params.append(competition)
        if season:
            conditions.append("season_name = ?")
            params.append(season)
        if position:
            conditions.append("position_name = ?")
            params.append(position)
        if team:
            conditions.append("team_name = ?")
            params.append(team)

        sql = f"""
            SELECT *
            FROM   vw_player_summary
            WHERE  {" AND ".join(conditions)}
            ORDER  BY xg_total DESC, goals DESC, total_passes DESC
        """
        return self.conn.execute(sql, params).df()

    def get_player_percentiles(
        self,
        competition: str | None = None,
        season: str | None = None,
        position: str | None = None,
        min_matches: int = 1,
    ) -> pd.DataFrame:
        """
        Return player percentile rankings from vw_player_percentiles.

        Percentile ranks are computed within position groups (PERCENT_RANK)
        and as overall decile buckets (NTILE). Players with fewer than
        min_matches appearances are excluded as statistically insufficient.

        Args:
            competition:  Filter by competition name.
            season:       Filter by season name.
            position:     Filter by position group.
            min_matches:  Minimum matches to include (default: 1).

        Returns:
            DataFrame ordered by overall_percentile DESC.
        """
        conditions = [f"matches_played >= {min_matches}"]
        params: list = []

        if competition:
            conditions.append("competition_name = ?")
            params.append(competition)
        if season:
            conditions.append("season_name = ?")
            params.append(season)
        if position:
            conditions.append("position_name = ?")
            params.append(position)

        sql = f"""
            SELECT *
            FROM   vw_player_percentiles
            WHERE  {" AND ".join(conditions)}
            ORDER  BY overall_percentile DESC
        """
        return self.conn.execute(sql, params).df()

    # ─────────────────────────────────────────────────────────────────────────
    # Team queries
    # ─────────────────────────────────────────────────────────────────────────

    def get_team_summary(
        self,
        competition: str | None = None,
        season: str | None = None,
    ) -> pd.DataFrame:
        """
        Return aggregated team statistics from vw_team_summary.

        Includes: wins/draws/losses, points, goals scored/conceded,
        xG for/against, and pass accuracy. One row per team per
        competition-season.

        Args:
            competition: Filter by competition name.
            season:      Filter by season name.

        Returns:
            DataFrame ordered by points DESC, goal_difference DESC.
        """
        conditions, params = ["1=1"], []
        if competition:
            conditions.append("competition_name = ?")
            params.append(competition)
        if season:
            conditions.append("season_name = ?")
            params.append(season)

        sql = f"""
            SELECT *
            FROM   vw_team_summary
            WHERE  {" AND ".join(conditions)}
            ORDER  BY points DESC, goal_difference DESC
        """
        return self.conn.execute(sql, params).df()

    # ─────────────────────────────────────────────────────────────────────────
    # Recruitment queries
    # ─────────────────────────────────────────────────────────────────────────

    def get_recruitment_candidates(
        self,
        competition: str | None = None,
        season: str | None = None,
        position: str | None = None,
        min_matches: int = 2,
        top_n: int | None = None,
    ) -> pd.DataFrame:
        """
        Return ranked recruitment candidates from vw_recruitment_candidates.

        Players are scored using a composite metric that weights xG output
        (40%), goal productivity (30%), and passing quality (30%).
        All scores are normalized to a 0–100 scale.

        Args:
            competition:  Filter by competition name.
            season:       Filter by season name.
            position:     Filter by position (e.g. "Center Forward").
            min_matches:  Minimum appearance threshold (default: 2).
            top_n:        If set, return only the top N candidates.

        Returns:
            DataFrame ordered by contribution_score DESC, position_rank ASC.
        """
        conditions = [f"matches_played >= {min_matches}"]
        params: list = []

        if competition:
            conditions.append("competition_name = ?")
            params.append(competition)
        if season:
            conditions.append("season_name = ?")
            params.append(season)
        if position:
            conditions.append("position_name = ?")
            params.append(position)

        limit = f"LIMIT {top_n}" if top_n else ""

        sql = f"""
            SELECT *
            FROM   vw_recruitment_candidates
            WHERE  {" AND ".join(conditions)}
            ORDER  BY contribution_score DESC, position_rank ASC
            {limit}
        """
        return self.conn.execute(sql, params).df()

    # ─────────────────────────────────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────────────────────────────────

    def list_views(self) -> list[str]:
        """Return the names of all views in the current DuckDB connection."""
        result = self.conn.execute(
            "SELECT view_name FROM duckdb_views() ORDER BY view_name"
        ).fetchall()
        return [row[0] for row in result]

    def get_player_by_id(self, player_id: int) -> pd.DataFrame:
        """Return full summary for a single player across all seasons."""
        return self.conn.execute(
            "SELECT * FROM vw_player_summary WHERE player_id = ?",
            [player_id],
        ).df()

    def execute(self, sql: str, params: list | None = None) -> pd.DataFrame:
        """
        Escape hatch for ad-hoc queries during development.

        Not intended for production use — prefer specific query methods above.
        Exists here rather than in calling code so SQL stays centralized.
        """
        return self.conn.execute(sql, params or []).df()
