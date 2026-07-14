"""
backend/ingestion/load_data.py — StatsBomb Open Data acquisition

Responsibility: Download StatsBomb Open Data into data/raw/.

This module is the ONLY place where external data is fetched.
All downstream modules consume processed files from data/raw/.

Usage:
    python -m backend.ingestion.load_data               # all competitions
    python -m backend.ingestion.load_data --competition "La Liga"
    python -m backend.ingestion.load_data --sample      # sample data only
    make data

StatsBomb Open Data license: CC BY-SA 4.0
https://github.com/statsbomb/open-data
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
SAMPLE_DIR = ROOT_DIR / "data" / "sample"

RAW_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core acquisition functions
# ─────────────────────────────────────────────────────────────────────────────


def fetch_competitions() -> pd.DataFrame:
    """
    Fetch all competitions available in StatsBomb Open Data.

    Returns a DataFrame with columns:
        competition_id, competition_name, country_name,
        season_id, season_name, match_available
    """
    from statsbombpy import sb

    logger.info("ingestion.competitions.start")
    competitions = sb.competitions()
    logger.info(
        "ingestion.competitions.complete",
        total=len(competitions),
    )
    return competitions


def fetch_matches(competition_id: int, season_id: int) -> pd.DataFrame:
    """
    Fetch all matches for a given competition and season.

    Args:
        competition_id: StatsBomb competition ID
        season_id: StatsBomb season ID

    Returns DataFrame with match metadata.
    """
    from statsbombpy import sb

    logger.info(
        "ingestion.matches.start",
        competition_id=competition_id,
        season_id=season_id,
    )
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    logger.info(
        "ingestion.matches.complete",
        competition_id=competition_id,
        season_id=season_id,
        total=len(matches),
    )
    return matches


def fetch_events(match_id: int) -> pd.DataFrame:
    """
    Fetch all events for a specific match.

    Args:
        match_id: StatsBomb match ID

    Returns DataFrame with event-level data.
    """
    from statsbombpy import sb

    logger.info("ingestion.events.start", match_id=match_id)
    events = sb.events(match_id=match_id)
    logger.info(
        "ingestion.events.complete",
        match_id=match_id,
        total_events=len(events),
    )
    return events


# ─────────────────────────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────────────────────────


def save_competitions(df: pd.DataFrame) -> Path:
    """Save competitions DataFrame to data/raw/competitions.csv."""
    out = RAW_DIR / "competitions.csv"
    df.to_csv(out, index=False)
    logger.info("ingestion.save", file=str(out), rows=len(df))
    return out


def save_matches(df: pd.DataFrame, competition_id: int, season_id: int) -> Path:
    """Save matches for a competition+season to data/raw/matches/."""
    match_dir = RAW_DIR / "matches"
    match_dir.mkdir(exist_ok=True)
    out = match_dir / f"{competition_id}_{season_id}.csv"
    df.to_csv(out, index=False)
    logger.info("ingestion.save", file=str(out), rows=len(df))
    return out


def save_events(df: pd.DataFrame, match_id: int) -> Path:
    """Save events for a match to data/raw/events/."""
    events_dir = RAW_DIR / "events"
    events_dir.mkdir(exist_ok=True)
    out = events_dir / f"{match_id}.parquet"
    df.to_parquet(out, index=False, engine="pyarrow")
    logger.info("ingestion.save", file=str(out), rows=len(df))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Sample dataset (for demonstration without full download)
# ─────────────────────────────────────────────────────────────────────────────

# StatsBomb Open Data: CC BY-SA 4.0 License
# Source: https://github.com/statsbomb/open-data
# The sample data in data/sample/ is redistributed under the same license.
# Attribution: StatsBomb — https://statsbomb.com

SAMPLE_COMPETITIONS = [
    {"competition_id": 11, "competition_name": "La Liga", "season_id": 90, "season_name": "2020/2021"},
    {"competition_id": 16, "competition_name": "Champions League", "season_id": 4, "season_name": "2018/2019"},
]


def load_sample_data() -> dict[str, pd.DataFrame]:
    """
    Load the small sample dataset from data/sample/.

    Returns a dict of DataFrames:
        {
            "competitions": DataFrame,
            "matches": DataFrame,
            "events": DataFrame  (first 3 matches only)
        }

    If sample files do not exist, falls back to fetching from StatsBomb
    for the first available competition.
    """
    sample_comps = SAMPLE_DIR / "competitions.csv"

    if sample_comps.exists():
        logger.info("ingestion.sample.load", source="local")
        competitions = pd.read_csv(sample_comps)
    else:
        logger.info(
            "ingestion.sample.missing",
            message="Sample files not found. Run: python -m backend.ingestion.load_data --sample",
        )
        competitions = pd.DataFrame(SAMPLE_COMPETITIONS)

    return {"competitions": competitions}


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline — targeted download
# ─────────────────────────────────────────────────────────────────────────────


def run_sample_pipeline() -> None:
    """
    Download a small representative sample:
    - All competitions metadata
    - Matches for La Liga 2020/21
    - Events for the first 5 matches (demonstration only)

    This is enough to run the full analytics pipeline locally.
    """
    logger.info("ingestion.pipeline.sample.start")

    # Step 1 — competitions
    competitions = fetch_competitions()
    save_competitions(competitions)

    # Step 2 — La Liga 2020/21 matches (competition_id=11, season_id=90)
    competition_id, season_id = 11, 90
    try:
        matches = fetch_matches(competition_id, season_id)
        save_matches(matches, competition_id, season_id)
    except Exception as exc:
        logger.warning(
            "ingestion.matches.skip",
            competition_id=competition_id,
            reason=str(exc),
        )
        return

    # Step 3 — events for first 5 matches
    sample_match_ids = matches["match_id"].head(5).tolist()
    for match_id in sample_match_ids:
        try:
            events = fetch_events(match_id)
            save_events(events, match_id)
            time.sleep(0.3)  # be polite to the StatsBomb API
        except Exception as exc:
            logger.warning(
                "ingestion.events.skip",
                match_id=match_id,
                reason=str(exc),
            )

    logger.info("ingestion.pipeline.sample.complete")


def run_full_pipeline(competition_filter: str | None = None) -> None:
    """
    Download the full StatsBomb Open Data catalogue.

    Args:
        competition_filter: If provided, only download this competition.
    """
    logger.info("ingestion.pipeline.full.start", filter=competition_filter)

    competitions = fetch_competitions()
    save_competitions(competitions)

    for _, row in competitions.iterrows():
        comp_name = row["competition_name"]
        comp_id = row["competition_id"]
        season_id = row["season_id"]

        if competition_filter and comp_name != competition_filter:
            continue

        try:
            matches = fetch_matches(comp_id, season_id)
            save_matches(matches, comp_id, season_id)

            for match_id in matches["match_id"].tolist():
                try:
                    events = fetch_events(match_id)
                    save_events(events, match_id)
                    time.sleep(0.2)
                except Exception as exc:
                    logger.warning(
                        "ingestion.events.skip",
                        match_id=match_id,
                        reason=str(exc),
                    )

        except Exception as exc:
            logger.warning(
                "ingestion.competition.skip",
                competition=comp_name,
                reason=str(exc),
            )

    logger.info("ingestion.pipeline.full.complete")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Athena — StatsBomb Open Data acquisition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.ingestion.load_data --sample
  python -m backend.ingestion.load_data --competition "La Liga"
  python -m backend.ingestion.load_data
        """,
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Download sample data only (5 matches, fast)",
    )
    parser.add_argument(
        "--competition",
        type=str,
        default=None,
        help="Download a specific competition (e.g. 'La Liga')",
    )
    args = parser.parse_args()

    if args.sample:
        run_sample_pipeline()
    else:
        run_full_pipeline(competition_filter=args.competition)


if __name__ == "__main__":
    main()
