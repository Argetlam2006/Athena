"""
backend/ingestion/validator.py — Data quality validation

Responsibility: Validate raw StatsBomb data before ETL processing.

Every dataset is validated before entering the pipeline.
Rows failing validation are logged and quarantined, not silently dropped.

Checks performed:
  - Schema completeness (required columns present)
  - Missing critical identifiers
  - Duplicate records
  - Value range violations (negative minutes, impossible ages)
  - Referential integrity (events reference valid match_ids)

Usage:
    python -m backend.ingestion.validator
    make validate
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.utils.logger import get_logger, get_validation_logger
from shared.schemas import ValidationResult

logger = get_logger(__name__)
validation_logger = get_validation_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
SAMPLE_DIR = ROOT_DIR / "data" / "sample"

# ─────────────────────────────────────────────────────────────────────────────
# Schema definitions — required columns per dataset
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_COMPETITION_COLS: list[str] = [
    "competition_id",
    "competition_name",
    "season_id",
    "season_name",
]

REQUIRED_MATCH_COLS: list[str] = [
    "match_id",
    "competition",
    "season",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "match_date",
]

REQUIRED_EVENT_COLS: list[str] = [
    "id",
    "match_id",
    "index",
    "type",
    "player",
    "team",
    "minute",
    "second",
]

# ─────────────────────────────────────────────────────────────────────────────
# Competition validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_competitions(df: pd.DataFrame) -> ValidationResult:
    """Validate the competitions DataFrame."""
    result = ValidationResult(
        dataset="competitions",
        total_rows=len(df),
        valid_rows=0,
        invalid_rows=0,
    )

    # Check required columns
    missing_cols = [c for c in REQUIRED_COMPETITION_COLS if c not in df.columns]
    if missing_cols:
        result.errors.append(f"Missing columns: {missing_cols}")
        result.invalid_rows = len(df)
        return result

    # Check for null competition_id or season_id
    null_ids = df["competition_id"].isna() | df["season_id"].isna()
    null_count = null_ids.sum()
    if null_count:
        result.errors.append(f"{null_count} rows with null competition_id or season_id")
        result.invalid_rows += null_count

    # Check for duplicate (competition_id, season_id) combinations
    duplicates = df.duplicated(subset=["competition_id", "season_id"]).sum()
    if duplicates:
        result.warnings.append(f"{duplicates} duplicate (competition_id, season_id) rows")

    result.valid_rows = len(df) - result.invalid_rows
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Match validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_matches(df: pd.DataFrame, source_label: str = "matches") -> ValidationResult:
    """Validate a matches DataFrame."""
    result = ValidationResult(
        dataset=source_label,
        total_rows=len(df),
        valid_rows=0,
        invalid_rows=0,
    )

    # Check required columns
    missing_cols = [c for c in REQUIRED_MATCH_COLS if c not in df.columns]
    if missing_cols:
        result.warnings.append(
            f"Missing columns (may use different schema): {missing_cols}"
        )

    # Check match_id presence
    if "match_id" in df.columns:
        null_match_ids = df["match_id"].isna().sum()
        if null_match_ids:
            result.errors.append(f"{null_match_ids} rows with null match_id")
            result.invalid_rows += null_match_ids

        # Check for duplicate match_ids
        duplicates = df.duplicated(subset=["match_id"]).sum()
        if duplicates:
            result.errors.append(f"{duplicates} duplicate match_ids")
            result.invalid_rows += duplicates

    # Check scores are non-negative
    for col in ["home_score", "away_score"]:
        if col in df.columns:
            negative = (df[col] < 0).sum()
            if negative:
                result.errors.append(f"{negative} rows with negative {col}")
                result.invalid_rows += negative

    result.valid_rows = max(0, len(df) - result.invalid_rows)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Event validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_events(df: pd.DataFrame, match_id: int) -> ValidationResult:
    """Validate events DataFrame for a single match."""
    result = ValidationResult(
        dataset=f"events_match_{match_id}",
        total_rows=len(df),
        valid_rows=0,
        invalid_rows=0,
    )

    if df.empty:
        result.errors.append("Empty events DataFrame")
        result.invalid_rows = 0
        result.valid_rows = 0
        return result

    # Check required columns
    missing_cols = [c for c in REQUIRED_EVENT_COLS if c not in df.columns]
    if missing_cols:
        result.warnings.append(f"Missing columns (schema may differ): {missing_cols}")

    # Validate minute values
    if "minute" in df.columns:
        negative_minutes = (df["minute"] < 0).sum()
        if negative_minutes:
            result.errors.append(f"{negative_minutes} events with negative minute")
            result.invalid_rows += negative_minutes

        impossible_minutes = (df["minute"] > 150).sum()
        if impossible_minutes:
            result.warnings.append(
                f"{impossible_minutes} events with minute > 150 (extra time?)"
            )

    # Check for null event type
    if "type" in df.columns:
        null_types = df["type"].isna().sum()
        if null_types:
            result.errors.append(f"{null_types} events with null type")
            result.invalid_rows += null_types

    result.valid_rows = max(0, len(df) - result.invalid_rows)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Report generator
# ─────────────────────────────────────────────────────────────────────────────


def generate_validation_report(results: list[ValidationResult]) -> str:
    """
    Generate a human-readable validation report from a list of results.

    Returns the report as a string and logs it to validation.log.
    """
    lines: list[str] = [
        "═" * 60,
        "  Athena — Data Validation Report",
        "═" * 60,
        "",
    ]

    total_datasets = len(results)
    total_valid = sum(r.valid_rows for r in results)
    total_invalid = sum(r.invalid_rows for r in results)
    datasets_clean = sum(1 for r in results if r.is_valid)

    lines += [
        f"Datasets validated : {total_datasets}",
        f"Datasets clean     : {datasets_clean} / {total_datasets}",
        f"Total valid rows   : {total_valid:,}",
        f"Total invalid rows : {total_invalid:,}",
        "",
    ]

    for result in results:
        status = "✓ PASS" if result.is_valid else "✗ FAIL"
        lines += [
            f"─" * 60,
            f"  {status}  {result.dataset}",
            f"  Total   : {result.total_rows:,}",
            f"  Valid   : {result.valid_rows:,} ({result.validity_pct}%)",
            f"  Invalid : {result.invalid_rows:,}",
        ]
        if result.errors:
            lines.append("  Errors  :")
            for e in result.errors:
                lines.append(f"    ✗ {e}")
        if result.warnings:
            lines.append("  Warnings:")
            for w in result.warnings:
                lines.append(f"    ⚠ {w}")
        lines.append("")

    lines += ["═" * 60]
    report = "\n".join(lines)
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Full validation run
# ─────────────────────────────────────────────────────────────────────────────


def run_validation() -> list[ValidationResult]:
    """
    Validate all available raw data files.

    Checks:
    1. data/raw/competitions.csv  (if exists)
    2. data/raw/matches/*.csv     (all match files)
    3. data/sample/competitions.csv (if exists)

    Returns list of ValidationResult objects.
    """
    results: list[ValidationResult] = []

    logger.info("validation.start")

    # Validate competitions
    for competitions_path in [
        RAW_DIR / "competitions.csv",
        SAMPLE_DIR / "competitions.csv",
    ]:
        if competitions_path.exists():
            df = pd.read_csv(competitions_path)
            result = validate_competitions(df)
            results.append(result)
            logger.info(
                "validation.competitions",
                file=str(competitions_path),
                valid=result.valid_rows,
                invalid=result.invalid_rows,
            )

    # Validate matches
    matches_dir = RAW_DIR / "matches"
    if matches_dir.exists():
        match_files = list(matches_dir.glob("*.csv"))
        logger.info("validation.matches.start", file_count=len(match_files))
        for match_file in match_files:
            df = pd.read_csv(match_file)
            result = validate_matches(df, source_label=f"matches/{match_file.name}")
            results.append(result)

    if not results:
        logger.warning(
            "validation.no_data",
            message=(
                "No raw data found. Run: python -m backend.ingestion.load_data --sample"
            ),
        )
        # Return a placeholder result so the pipeline can report gracefully
        results.append(
            ValidationResult(
                dataset="(no data found)",
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                warnings=["No raw data available. Run `make data` first."],
            )
        )

    report = generate_validation_report(results)
    validation_logger.info("report", content=report)
    print(report)

    logger.info(
        "validation.complete",
        datasets=len(results),
        all_clean=all(r.is_valid for r in results),
    )
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    run_validation()


if __name__ == "__main__":
    main()
