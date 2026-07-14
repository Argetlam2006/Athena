"""
backend/etl/pipeline.py — ETL pipeline orchestrator

Reads raw StatsBomb JSON from data/raw/, normalizes into typed DataFrames,
and writes analytical Parquet files to data/processed/.

Output files:
    data/processed/competitions.parquet  — all competition-season rows
    data/processed/matches.parquet       — all matches (flattened)
    data/processed/events.parquet        — all events (wide format)
    data/processed/lineups.parquet       — all player appearances

The pipeline is driven by data/raw/manifest.json, which records exactly
what was downloaded in Sprint 1.1. Only files recorded in the manifest
are processed, making the ETL deterministic and repeatable.

Usage:
    python -m backend.etl.pipeline
    python -m backend.etl.pipeline --force
    make etl
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backend.etl.normalize import (
    normalize_competitions,
    normalize_events,
    normalize_lineups,
    normalize_matches,
)
from backend.ingestion.manifest import ManifestManager
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR      = Path(__file__).resolve().parents[2]
RAW_DIR       = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

# ─────────────────────────────────────────────────────────────────────────────
# Result summary
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ETLSummary:
    """
    Records what was produced by one ETL run.
    """
    competitions_rows: int = 0
    matches_rows:      int = 0
    events_rows:       int = 0
    lineups_rows:      int = 0
    matches_processed: int = 0
    matches_failed:    int = 0
    output_dir:        str = ""

    def report_lines(self) -> list[str]:
        return [
            f"  Output directory   : {self.output_dir}",
            f"  competitions.parquet : {self.competitions_rows:,} rows",
            f"  matches.parquet      : {self.matches_rows:,} rows",
            f"  events.parquet       : {self.events_rows:,} rows",
            f"  lineups.parquet      : {self.lineups_rows:,} rows",
            f"  Matches processed    : {self.matches_processed}",
            f"  Matches failed       : {self.matches_failed}",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> list | dict | None:
    """Load JSON from path. Returns None on failure (logged)."""
    import json
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("etl.load_json.fail", path=str(path), reason=str(exc)[:120])
        return None


def _save_parquet(df: pd.DataFrame, path: Path, label: str) -> None:
    """Write DataFrame to Parquet. Creates parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")
    logger.info("etl.save", file=path.name, rows=len(df), size_kb=round(path.stat().st_size / 1024, 1))
    print(f"  ✓ {label:<28} {len(df):>8,} rows  →  {path.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline steps
# ─────────────────────────────────────────────────────────────────────────────


def _run_competitions(raw_dir: Path, processed_dir: Path) -> pd.DataFrame:
    """Step 1: Normalize and save competitions."""
    data = _load_json(raw_dir / "competitions.json")
    if not data:
        logger.warning("etl.competitions.missing")
        return pd.DataFrame()

    df = normalize_competitions(data)
    _save_parquet(df, processed_dir / "competitions.parquet", "competitions")
    return df


def _run_matches(raw_dir: Path, processed_dir: Path) -> pd.DataFrame:
    """
    Step 2: Normalize and save all matches.

    Discovers match files by scanning data/raw/matches/ recursively.
    Each file covers one competition+season.
    """
    matches_dir = raw_dir / "matches"
    if not matches_dir.exists():
        logger.warning("etl.matches.dir_missing")
        return pd.DataFrame()

    all_frames: list[pd.DataFrame] = []
    match_files = sorted(matches_dir.rglob("*.json"))

    logger.info("etl.matches.start", files=len(match_files))
    for mf in match_files:
        data = _load_json(mf)
        if not data:
            continue
        df = normalize_matches(data)
        if not df.empty:
            all_frames.append(df)

    if not all_frames:
        logger.warning("etl.matches.empty")
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True).drop_duplicates(subset=["match_id"])
    _save_parquet(combined, processed_dir / "matches.parquet", "matches")
    return combined


def _run_events(
    raw_dir: Path,
    processed_dir: Path,
    match_ids: list[int],
) -> tuple[pd.DataFrame, int, int]:
    """
    Step 3: Normalize and save all events.

    Processes match IDs recorded in the manifest.
    Returns (DataFrame, matches_processed, matches_failed).
    """
    events_dir = raw_dir / "events"
    if not events_dir.exists():
        logger.warning("etl.events.dir_missing")
        return pd.DataFrame(), 0, 0

    all_frames: list[pd.DataFrame] = []
    processed = 0
    failed = 0

    logger.info("etl.events.start", match_count=len(match_ids))
    for match_id in match_ids:
        path = events_dir / f"{match_id}.json"
        if not path.exists():
            logger.warning("etl.events.missing", match_id=match_id)
            failed += 1
            continue

        data = _load_json(path)
        if not data:
            failed += 1
            continue

        df = normalize_events(data, match_id)
        if not df.empty:
            all_frames.append(df)
        processed += 1

    if not all_frames:
        logger.warning("etl.events.empty")
        return pd.DataFrame(), processed, failed

    combined = pd.concat(all_frames, ignore_index=True)
    _save_parquet(combined, processed_dir / "events.parquet", "events")
    return combined, processed, failed


def _run_lineups(
    raw_dir: Path,
    processed_dir: Path,
    match_ids: list[int],
) -> pd.DataFrame:
    """
    Step 4: Normalize and save all lineups.

    Processes match IDs recorded in the manifest.
    """
    lineups_dir = raw_dir / "lineups"
    if not lineups_dir.exists():
        logger.warning("etl.lineups.dir_missing")
        return pd.DataFrame()

    all_frames: list[pd.DataFrame] = []

    logger.info("etl.lineups.start", match_count=len(match_ids))
    for match_id in match_ids:
        path = lineups_dir / f"{match_id}.json"
        if not path.exists():
            logger.warning("etl.lineups.missing", match_id=match_id)
            continue

        data = _load_json(path)
        if not data:
            continue

        df = normalize_lineups(data, match_id)
        if not df.empty:
            all_frames.append(df)

    if not all_frames:
        logger.warning("etl.lineups.empty")
        return pd.DataFrame()

    combined = pd.concat(all_frames, ignore_index=True).drop_duplicates(
        subset=["match_id", "player_id", "team_id"]
    )
    _save_parquet(combined, processed_dir / "lineups.parquet", "lineups")
    return combined


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def run_etl(
    raw_dir: Path = RAW_DIR,
    processed_dir: Path = PROCESSED_DIR,
    force: bool = False,
) -> ETLSummary:
    """
    Run the complete ETL pipeline.

    Reads from raw_dir (data/raw/), writes Parquet to processed_dir (data/processed/).

    The pipeline is driven by data/raw/manifest.json, which records exactly
    which competitions and matches were downloaded in the ingestion step.

    Args:
        raw_dir:       Source directory (data/raw/).
        processed_dir: Destination directory (data/processed/).
        force:         If True, overwrite existing Parquet files.
                       If False, skip steps whose output already exists.

    Returns:
        ETLSummary with row counts and status for each output file.
    """
    summary = ETLSummary(output_dir=str(processed_dir))
    processed_dir.mkdir(parents=True, exist_ok=True)

    logger.info("etl.start", raw_dir=str(raw_dir), processed_dir=str(processed_dir))
    print()
    print("  ══════════════════════════════════════════════════════")
    print("    Athena ETL Pipeline — Phase 2.1")
    print("  ══════════════════════════════════════════════════════")

    # Determine which match IDs to process from manifest
    manager = ManifestManager(raw_dir)
    manifest = manager.load()
    match_ids = manifest.all_match_ids()

    if not match_ids:
        # Fall back to scanning the events directory if manifest is empty
        events_dir = raw_dir / "events"
        if events_dir.exists():
            match_ids = [int(p.stem) for p in events_dir.glob("*.json") if p.stem.isdigit()]
            logger.info("etl.match_ids.from_scan", count=len(match_ids))
        else:
            logger.warning(
                "etl.no_data",
                message="No data found. Run `make data` before `make etl`.",
            )
            print()
            print("  ⚠ No data found in data/raw/. Run `make data` first.")
            print()
            return summary

    logger.info("etl.scope", match_count=len(match_ids), competition_count=len(manifest.competitions))

    # Step 1 — Competitions
    if force or not (processed_dir / "competitions.parquet").exists():
        comp_df = _run_competitions(raw_dir, processed_dir)
        summary.competitions_rows = len(comp_df)
    else:
        existing = pd.read_parquet(processed_dir / "competitions.parquet")
        summary.competitions_rows = len(existing)
        print(f"  ↷ competitions.parquet        {summary.competitions_rows:>8,} rows  (skipped, exists)")

    # Step 2 — Matches
    if force or not (processed_dir / "matches.parquet").exists():
        matches_df = _run_matches(raw_dir, processed_dir)
        summary.matches_rows = len(matches_df)
    else:
        existing = pd.read_parquet(processed_dir / "matches.parquet")
        summary.matches_rows = len(existing)
        print(f"  ↷ matches.parquet             {summary.matches_rows:>8,} rows  (skipped, exists)")

    # Step 3 — Events
    if force or not (processed_dir / "events.parquet").exists():
        events_df, processed_count, failed_count = _run_events(raw_dir, processed_dir, match_ids)
        summary.events_rows      = len(events_df)
        summary.matches_processed = processed_count
        summary.matches_failed    = failed_count
    else:
        existing = pd.read_parquet(processed_dir / "events.parquet")
        summary.events_rows = len(existing)
        print(f"  ↷ events.parquet              {summary.events_rows:>8,} rows  (skipped, exists)")

    # Step 4 — Lineups
    if force or not (processed_dir / "lineups.parquet").exists():
        lineups_df = _run_lineups(raw_dir, processed_dir, match_ids)
        summary.lineups_rows = len(lineups_df)
    else:
        existing = pd.read_parquet(processed_dir / "lineups.parquet")
        summary.lineups_rows = len(existing)
        print(f"  ↷ lineups.parquet             {summary.lineups_rows:>8,} rows  (skipped, exists)")

    # Final summary
    print()
    print("  ──────────────────────────────────────────────────────")
    print("  ETL complete.")
    for line in summary.report_lines():
        print(line)
    print("  ══════════════════════════════════════════════════════")
    print()

    logger.info(
        "etl.complete",
        competitions=summary.competitions_rows,
        matches=summary.matches_rows,
        events=summary.events_rows,
        lineups=summary.lineups_rows,
    )
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Athena ETL Pipeline — normalize StatsBomb JSON to Parquet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.etl.pipeline
  python -m backend.etl.pipeline --force
  make etl
        """,
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Parquet files (default: skip existing)",
    )
    args = parser.parse_args()
    run_etl(force=args.force)


if __name__ == "__main__":
    main()
