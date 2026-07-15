"""
backend/warehouse/connection.py — DuckDB connection management

Provides a context manager for DuckDB connections so every caller
opens and closes connections safely without boilerplate.

Usage:
    from backend.warehouse.connection import connect

    with connect() as conn:
        df = conn.execute("SELECT * FROM vw_player_summary").df()

    # Test/override with specific path:
    with connect(db_path=":memory:") as conn:
        ...
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import duckdb

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "warehouse" / "athena.duckdb"


# ─────────────────────────────────────────────────────────────────────────────
# Connection factory
# ─────────────────────────────────────────────────────────────────────────────


@contextmanager
def connect(
    db_path: str | Path = DB_PATH,
    read_only: bool = False,
) -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """
    Context manager that yields an open DuckDB connection.

    Automatically closes the connection on exit, even if an exception
    is raised. On the first call to a new database file, DuckDB creates
    the file automatically.

    Args:
        db_path:   Path to the DuckDB file.
                   Use ":memory:" for an in-memory database (tests, CI).
        read_only: If True, opens in read-only mode (allows concurrent readers).

    Yields:
        An open duckdb.DuckDBPyConnection.

    Example:
        with connect() as conn:
            df = conn.execute("SELECT * FROM vw_player_summary").df()
    """
    path = str(db_path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(database=path, read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()
