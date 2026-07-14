"""
backend/warehouse — Athena Analytics Warehouse

Single entry point for all analytical data access.

Architecture:
    Parquet (data/processed/)
        ↓  zero-copy registration
    DuckDB (data/warehouse/athena.duckdb)
        ↓  CREATE OR REPLACE VIEW (sql/views/*.sql)
    vw_match_summary, vw_player_summary, vw_team_summary,
    vw_player_percentiles, vw_recruitment_candidates
        ↓  WarehouseQueries (parameterized DataFrames)
    Analytics Engine / Streamlit UI

Quick start:
    from backend.warehouse import Warehouse

    wh = Warehouse().build()
    df = wh.player_summary(competition="La Liga")
    df = wh.player_percentiles(min_matches=3)
    df = wh.recruitment_candidates(position="Center Forward", top_n=20)
"""

from backend.warehouse.connection import connect
from backend.warehouse.queries import WarehouseQueries
from backend.warehouse.warehouse import Warehouse

__all__ = [
    "Warehouse",
    "WarehouseQueries",
    "connect",
]
