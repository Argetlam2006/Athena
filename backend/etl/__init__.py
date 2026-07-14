"""
backend/etl — ETL pipeline: normalize StatsBomb JSON → analytical Parquet.

Public API:
    # Normalization functions (pure transform, no I/O):
    from backend.etl.normalize import normalize_competitions, normalize_matches
    from backend.etl.normalize import normalize_events, normalize_lineups

    # Pipeline runner (reads raw_dir, writes processed_dir):
    from backend.etl.pipeline import run_etl
"""

from backend.etl.normalize import (
    normalize_competitions,
    normalize_events,
    normalize_lineups,
    normalize_matches,
)

__all__ = [
    "normalize_competitions",
    "normalize_matches",
    "normalize_events",
    "normalize_lineups",
]
