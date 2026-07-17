"""
backend/warehouse/warehouse.py - Athena Analytics Warehouse

The Warehouse class is the single entry point for all analytical data access.
It manages the DuckDB lifecycle: registering Parquet files as base views,
creating analytical SQL views, and exposing a clean query interface.

Architecture
------------
  Parquet (data/processed/)
      ↓  registered as DuckDB base views
  DuckDB (data/warehouse/athena.duckdb)
      ↓  CREATE OR REPLACE VIEW ... (sql/views/*.sql)
  Analytical views (vw_player_summary, vw_team_summary, etc.)
      ↓  WarehouseQueries (parameterized DataFrames)
  Analytics Engine / Streamlit UI

Why DuckDB
----------
  • Column-oriented - extremely fast aggregations on event-level data.
  • Zero-copy Parquet scanning - reads directly from .parquet files with
    no data loading overhead.
  • Analytical SQL - QUALIFY, FILTER, PERCENT_RANK, NTILE out of the box.
  • Embedded - no server to run; one file, zero infrastructure.

Usage
-----
    from backend.warehouse.warehouse import Warehouse

    wh = Warehouse()
    wh.build()                                     # register + create views

    df = wh.query.get_player_summary(competition="La Liga")
    df = wh.query.get_player_percentiles(min_matches=3)
    df = wh.query.get_recruitment_candidates(position="Center Forward")
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

from backend.utils.logger import get_logger
from backend.warehouse.connection import DB_PATH, connect
from backend.warehouse.queries import WarehouseQueries

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
SQL_VIEWS_DIR = ROOT_DIR / "sql" / "views"

# Base tables (Parquet) that must exist before analytical views are created
BASE_TABLES = ["competitions", "matches", "events", "lineups"]


# -----------------------------------------------------------------------------
# Warehouse
# -----------------------------------------------------------------------------


class Warehouse:
    """
    Athena Analytics Warehouse.

    Wraps a DuckDB database that sits directly on top of the Phase 2.1
    Parquet layer. Views are created from modular SQL files in sql/views/
    and are re-created (idempotently) on every call to build().

    Args:
        db_path:       Path to DuckDB file. Defaults to data/warehouse/athena.duckdb.
        processed_dir: Directory containing Parquet files. Defaults to data/processed/.
        _conn:         Override connection for testing (use in-memory DuckDB).

    Attributes:
        query: WarehouseQueries instance bound to the current connection.
               Only available inside a context-manager block or after build().
    """

    def __init__(
        self,
        db_path: str | Path = DB_PATH,
        processed_dir: str | Path = PROCESSED_DIR,
        _conn: duckdb.DuckDBPyConnection | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.processed_dir = Path(processed_dir)
        self._test_conn = _conn  # injected for unit tests (in-memory DuckDB)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def build(self) -> Warehouse:
        """
        Initialize the warehouse: register Parquet files and create all
        analytical views. Idempotent - safe to call repeatedly.

        Returns self for convenient chaining:
            wh = Warehouse().build()

        Raises:
            FileNotFoundError: If no Parquet files exist in processed_dir.
                               Run `make etl` first.
        """
        if self._test_conn is not None:
            self._setup(self._test_conn)
            return self

        with connect(self.db_path) as conn:
            self._setup(conn)
        return self

    def _setup(self, conn: duckdb.DuckDBPyConnection) -> None:
        """Register Parquet + create all analytical views on conn."""
        registered = self._register_parquet(conn)
        if not registered:
            logger.warning(
                "warehouse.build.no_parquet",
                message="No Parquet files found. Run `make etl` first.",
                dir=str(self.processed_dir),
            )
            return
        created = self._create_views(conn)
        logger.info(
            "warehouse.build.complete",
            base_tables=len(registered),
            views_created=len(created),
        )

    def _register_parquet(self, conn: duckdb.DuckDBPyConnection) -> list[str]:
        """
        Register each Parquet file as a DuckDB view using read_parquet().

        This is zero-copy: DuckDB scans the Parquet file lazily at query time.
        The resulting view named after the table (e.g. 'events') becomes the
        base for all downstream analytical views.

        Returns the list of table names successfully registered.
        """
        registered = []
        for table in BASE_TABLES:
            path = self.processed_dir / f"{table}.parquet"
            if not path.exists():
                logger.warning("warehouse.parquet.missing", table=table, path=str(path))
                continue

            # Use POSIX paths in SQL - DuckDB handles forward slashes on Windows
            conn.execute(f"""
                CREATE OR REPLACE VIEW {table} AS
                SELECT * FROM read_parquet('{path.as_posix()}')
            """)
            registered.append(table)
            logger.info("warehouse.parquet.registered", table=table)

        return registered

    def _create_views(self, conn: duckdb.DuckDBPyConnection) -> list[str]:
        """
        Load and execute all SQL view definition files from sql/views/.

        Files are executed in alphabetical order (01_, 02_, ... prefix)
        so that dependent views are always created after their dependencies.

        Returns the list of SQL filenames executed.
        """
        if not SQL_VIEWS_DIR.exists():
            logger.warning("warehouse.sql_dir.missing", path=str(SQL_VIEWS_DIR))
            return []

        executed = []
        for sql_file in sorted(SQL_VIEWS_DIR.glob("*.sql")):
            sql = sql_file.read_text(encoding="utf-8").strip()
            if not sql:
                continue
            try:
                conn.execute(sql)
                executed.append(sql_file.name)
                logger.info("warehouse.view.created", file=sql_file.name)
            except Exception as exc:
                logger.error(
                    "warehouse.view.error",
                    file=sql_file.name,
                    reason=str(exc)[:200],
                )
                raise

        return executed

    # -------------------------------------------------------------------------
    # Query interface
    # -------------------------------------------------------------------------

    def _open_query_conn(self) -> duckdb.DuckDBPyConnection:
        """Open a fresh connection to the warehouse file."""
        if self._test_conn is not None:
            return self._test_conn
        return duckdb.connect(str(self.db_path))

    @property
    def query(self) -> WarehouseQueries:
        """
        Returns a WarehouseQueries instance bound to a new connection.

        Note: the returned object opens a connection that is NOT closed
        automatically. For long-running processes, prefer the explicit pattern:

            with connect() as conn:
                q = WarehouseQueries(conn)
                df = q.get_player_summary()
        """
        return WarehouseQueries(self._open_query_conn())

    # -------------------------------------------------------------------------
    # Convenience pass-throughs (avoids one layer of indirection for callers)
    # -------------------------------------------------------------------------

    def player_summary(self, **kwargs) -> pd.DataFrame:
        """Shorthand for wh.query.get_player_summary(**kwargs)."""
        conn = self._open_query_conn()
        return WarehouseQueries(conn).get_player_summary(**kwargs)

    def team_summary(self, **kwargs) -> pd.DataFrame:
        """Shorthand for wh.query.get_team_summary(**kwargs)."""
        conn = self._open_query_conn()
        return WarehouseQueries(conn).get_team_summary(**kwargs)

    def match_summary(self, **kwargs) -> pd.DataFrame:
        """Shorthand for wh.query.get_match_summary(**kwargs)."""
        conn = self._open_query_conn()
        return WarehouseQueries(conn).get_match_summary(**kwargs)

    def player_percentiles(self, **kwargs) -> pd.DataFrame:
        """Shorthand for wh.query.get_player_percentiles(**kwargs)."""
        conn = self._open_query_conn()
        return WarehouseQueries(conn).get_player_percentiles(**kwargs)

    def recruitment_candidates(self, **kwargs) -> pd.DataFrame:
        """Shorthand for wh.query.get_recruitment_candidates(**kwargs)."""
        conn = self._open_query_conn()
        return WarehouseQueries(conn).get_recruitment_candidates(**kwargs)

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    def info(self) -> dict:
        """Return basic warehouse metadata for diagnostics."""
        try:
            conn = self._open_query_conn()
            views = WarehouseQueries(conn).list_views()
            return {
                "db_path": str(self.db_path),
                "processed_dir": str(self.processed_dir),
                "views": views,
                "db_exists": self.db_path.exists(),
            }
        except Exception as exc:
            return {"error": str(exc)}


# -----------------------------------------------------------------------------
# CLI entry point
# -----------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Athena Analytics Warehouse - initialize DuckDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.warehouse.warehouse          # Build / refresh warehouse
  python -m backend.warehouse.warehouse --info   # Print warehouse metadata
  make warehouse
        """,
    )
    parser.add_argument(
        "--info", action="store_true", help="Print warehouse info and exit"
    )
    args = parser.parse_args()

    wh = Warehouse()

    if args.info:
        meta = wh.info()
        print()
        print("  Athena Warehouse Info")
        print("  ---------------------")
        for k, v in meta.items():
            if isinstance(v, list):
                print(f"  {k}: {', '.join(v) if v else 'none'}")
            else:
                print(f"  {k}: {v}")
        print()
        return

    print()
    print("  ======================================================")
    print("    Athena Analytics Warehouse - Phase 2.2")
    print("  ======================================================")
    wh.build()
    meta = wh.info()
    print(f"  OK DuckDB: {meta['db_path']}")
    print(f"  OK Views:  {', '.join(meta.get('views', []))}")
    print("  ======================================================")
    print()
    sys.exit(0)


if __name__ == "__main__":
    main()
