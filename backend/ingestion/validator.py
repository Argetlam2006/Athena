"""
backend/ingestion/validator.py — Data quality validation

Two validation layers:

  Layer A — File validation (Sprint 1.1, run_validation)
    Validates the raw JSON files in data/raw/.
    Called after load_data.py completes.
    Checks: file integrity, JSON parsability, StatsBomb schema fields,
            manifest cross-references, referential integrity.

  Layer B — DataFrame validation (Sprint 1.3 ETL, validate_competitions etc.)
    Validates pandas DataFrames produced by the ETL pipeline.
    Kept intact for downstream use.

Usage:
    python -m backend.ingestion.validator         # validate data/raw/
    make validate
"""

from __future__ import annotations

import json
import sys
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

# ─────────────────────────────────────────────────────────────────────────────
# Layer A — StatsBomb JSON field requirements
# ─────────────────────────────────────────────────────────────────────────────

#: Required top-level keys in every competitions.json entry
REQUIRED_COMPETITION_KEYS: set[str] = {
    "competition_id",
    "competition_name",
    "season_id",
    "season_name",
}

#: Required top-level keys in every matches/{comp}/{season}.json entry
REQUIRED_MATCH_KEYS: set[str] = {
    "match_id",
    "match_date",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
}

#: Required top-level keys in every event inside events/{match_id}.json
REQUIRED_EVENT_KEYS: set[str] = {
    "id",
    "index",
    "type",
    "minute",
    "second",
}

#: Required top-level keys in every lineup entry inside lineups/{match_id}.json
REQUIRED_LINEUP_KEYS: set[str] = {
    "team_id",
    "team_name",
    "lineup",
}


# ─────────────────────────────────────────────────────────────────────────────
# Layer A helpers — read and check individual JSON files
# ─────────────────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> tuple[list | dict | None, str | None]:
    """
    Parse a JSON file.

    Returns:
        (data, None)        — success
        (None, error_msg)   — parse failure
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error at line {exc.lineno}: {exc.msg}"
    except OSError as exc:
        return None, f"File read error: {exc}"


def _check_required_keys(record: dict, required: set[str], label: str) -> list[str]:
    """Return list of error strings for any missing required keys."""
    missing = required - record.keys()
    if missing:
        return [f"{label}: missing keys {sorted(missing)}"]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Layer A — File-level validators
# ─────────────────────────────────────────────────────────────────────────────


def validate_competitions_file(raw_dir: Path = RAW_DIR) -> ValidationResult:
    """
    Validate data/raw/competitions.json.

    Checks:
      - File exists
      - Valid JSON
      - Top-level is a non-empty list
      - Each entry has required keys
      - No duplicate (competition_id, season_id) pairs
    """
    path = raw_dir / "competitions.json"
    result = ValidationResult(
        dataset="competitions.json",
        total_rows=0,
        valid_rows=0,
        invalid_rows=0,
    )

    if not path.exists():
        result.errors.append("File not found: competitions.json")
        return result

    data, err = _load_json(path)
    if err:
        result.errors.append(err)
        return result

    if not isinstance(data, list):
        result.errors.append("Expected a JSON array at root, got object")
        return result

    result.total_rows = len(data)

    if result.total_rows == 0:
        result.errors.append("competitions.json is empty")
        return result

    seen_pairs: set[tuple] = set()
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            result.errors.append(
                f"Entry {i}: expected object, got {type(entry).__name__}"
            )
            result.invalid_rows += 1
            continue

        errs = _check_required_keys(entry, REQUIRED_COMPETITION_KEYS, f"Entry {i}")
        if errs:
            result.errors.extend(errs)
            result.invalid_rows += 1
            continue

        pair = (entry.get("competition_id"), entry.get("season_id"))
        if pair in seen_pairs:
            result.warnings.append(
                f"Duplicate (competition_id, season_id) = {pair} at entry {i}"
            )
        seen_pairs.add(pair)

    result.valid_rows = max(0, result.total_rows - result.invalid_rows)
    return result


def validate_matches_file(
    path: Path, competition_id: int, season_id: int
) -> ValidationResult:
    """
    Validate a single data/raw/matches/{competition_id}/{season_id}.json file.

    Checks:
      - Valid JSON
      - Top-level is a list
      - Each match has required keys
      - match_id values are unique
      - Scores are non-negative integers
    """
    label = f"matches/{competition_id}/{season_id}.json"
    result = ValidationResult(
        dataset=label,
        total_rows=0,
        valid_rows=0,
        invalid_rows=0,
    )

    if not path.exists():
        result.errors.append(f"File not found: {label}")
        return result

    data, err = _load_json(path)
    if err:
        result.errors.append(err)
        return result

    if not isinstance(data, list):
        result.errors.append("Expected a JSON array at root")
        return result

    result.total_rows = len(data)

    if result.total_rows == 0:
        result.warnings.append(f"{label} contains no matches")
        return result

    seen_ids: set = set()
    for i, match in enumerate(data):
        if not isinstance(match, dict):
            result.errors.append(f"Match {i}: expected object")
            result.invalid_rows += 1
            continue

        errs = _check_required_keys(match, REQUIRED_MATCH_KEYS, f"Match {i}")
        if errs:
            result.errors.extend(errs)
            result.invalid_rows += 1
            continue

        mid = match.get("match_id")
        if mid in seen_ids:
            result.errors.append(f"Duplicate match_id {mid}")
            result.invalid_rows += 1
        seen_ids.add(mid)

        # Score range checks
        for score_key in ("home_score", "away_score"):
            score = match.get(score_key)
            if isinstance(score, (int, float)) and score < 0:
                result.errors.append(f"Match {mid}: {score_key} is negative ({score})")
                result.invalid_rows += 1

    result.valid_rows = max(0, result.total_rows - result.invalid_rows)
    return result


def validate_events_file(path: Path, match_id: int) -> ValidationResult:
    """
    Validate a single data/raw/events/{match_id}.json file.

    Checks:
      - Valid JSON
      - Top-level is a non-empty list
      - Each event has required keys
      - minute values are non-negative
      - No duplicate event IDs
    """
    label = f"events/{match_id}.json"
    result = ValidationResult(
        dataset=label,
        total_rows=0,
        valid_rows=0,
        invalid_rows=0,
    )

    if not path.exists():
        result.errors.append(f"File not found: {label}")
        return result

    data, err = _load_json(path)
    if err:
        result.errors.append(err)
        return result

    if not isinstance(data, list):
        result.errors.append("Expected a JSON array at root")
        return result

    result.total_rows = len(data)

    if result.total_rows == 0:
        result.errors.append(f"{label} is empty (no events)")
        return result

    seen_ids: set = set()
    for i, event in enumerate(data):
        if not isinstance(event, dict):
            result.errors.append(f"Event {i}: expected object")
            result.invalid_rows += 1
            continue

        errs = _check_required_keys(event, REQUIRED_EVENT_KEYS, f"Event {i}")
        if errs:
            result.errors.extend(errs)
            result.invalid_rows += 1
            continue

        eid = event.get("id")
        if eid in seen_ids:
            result.errors.append(f"Duplicate event id {eid!r}")
            result.invalid_rows += 1
        seen_ids.add(eid)

        minute = event.get("minute")
        if isinstance(minute, (int, float)):
            if minute < 0:
                result.errors.append(f"Event {eid!r}: minute is negative ({minute})")
                result.invalid_rows += 1
            elif minute > 150:
                result.warnings.append(
                    f"Event {eid!r}: minute={minute} (> 150, possible deep extra time)"
                )

    result.valid_rows = max(0, result.total_rows - result.invalid_rows)
    return result


def validate_lineups_file(path: Path, match_id: int) -> ValidationResult:
    """
    Validate a single data/raw/lineups/{match_id}.json file.

    Checks:
      - Valid JSON
      - Top-level is a list
      - Exactly 2 entries (one per team)
      - Each entry has required keys (team_id, team_name, lineup)
      - Each lineup entry is a list
    """
    label = f"lineups/{match_id}.json"
    result = ValidationResult(
        dataset=label,
        total_rows=0,
        valid_rows=0,
        invalid_rows=0,
    )

    if not path.exists():
        result.errors.append(f"File not found: {label}")
        return result

    data, err = _load_json(path)
    if err:
        result.errors.append(err)
        return result

    if not isinstance(data, list):
        result.errors.append("Expected a JSON array at root")
        return result

    result.total_rows = len(data)

    if result.total_rows == 0:
        result.errors.append(f"{label} is empty")
        return result

    if result.total_rows != 2:
        result.warnings.append(
            f"{label} has {result.total_rows} team entries (expected 2)"
        )

    for i, team_entry in enumerate(data):
        if not isinstance(team_entry, dict):
            result.errors.append(f"Entry {i}: expected object")
            result.invalid_rows += 1
            continue

        errs = _check_required_keys(team_entry, REQUIRED_LINEUP_KEYS, f"Team entry {i}")
        if errs:
            result.errors.extend(errs)
            result.invalid_rows += 1
            continue

        if not isinstance(team_entry.get("lineup"), list):
            result.errors.append(
                f"Team {team_entry.get('team_name', i)!r}: 'lineup' is not a list"
            )
            result.invalid_rows += 1

    result.valid_rows = max(0, result.total_rows - result.invalid_rows)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Layer A — Cross-reference and manifest checks
# ─────────────────────────────────────────────────────────────────────────────


def validate_manifest_consistency(raw_dir: Path = RAW_DIR) -> ValidationResult:
    """
    Check that the manifest is consistent with actual files on disk.

    For every match_id recorded in the manifest:
      - events/{match_id}.json must exist
      - lineups/{match_id}.json must exist

    For every competition in the manifest:
      - matches/{comp_id}/{season_id}.json must exist
    """
    from backend.ingestion.manifest import ManifestManager

    result = ValidationResult(
        dataset="manifest.json",
        total_rows=0,
        valid_rows=0,
        invalid_rows=0,
    )

    manager = ManifestManager(raw_dir)
    if not manager.exists():
        result.warnings.append(
            "manifest.json not found — download hasn't run yet or was not recorded"
        )
        return result

    manifest = manager.load()

    # Check competitions — match files
    for comp in manifest.competitions:
        match_path = (
            raw_dir / "matches" / str(comp.competition_id) / f"{comp.season_id}.json"
        )
        if not match_path.exists():
            result.errors.append(
                f"Manifest records matches/{comp.competition_id}/{comp.season_id}.json "
                f"but file is missing"
            )
            result.invalid_rows += 1
        else:
            result.valid_rows += 1

    # Check events and lineups
    for match_id in manifest.events_downloaded:
        result.total_rows += 1
        events_path = raw_dir / "events" / f"{match_id}.json"
        if not events_path.exists():
            result.errors.append(
                f"Manifest records events/{match_id}.json but file is missing"
            )
            result.invalid_rows += 1
        else:
            result.valid_rows += 1

    for match_id in manifest.lineups_downloaded:
        result.total_rows += 1
        lineups_path = raw_dir / "lineups" / f"{match_id}.json"
        if not lineups_path.exists():
            result.errors.append(
                f"Manifest records lineups/{match_id}.json but file is missing"
            )
            result.invalid_rows += 1
        else:
            result.valid_rows += 1

    result.total_rows += len(manifest.competitions)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Layer A — Full directory validation
# ─────────────────────────────────────────────────────────────────────────────


def validate_raw_directory(raw_dir: Path = RAW_DIR) -> list[ValidationResult]:
    """
    Validate all raw JSON files present in data/raw/.

    Steps:
      1. Validate competitions.json
      2. Validate every matches/{comp_id}/{season_id}.json file
      3. Sample-validate events (up to MAX_EVENTS_SAMPLE files)
      4. Sample-validate lineups (up to MAX_LINEUPS_SAMPLE files)
      5. Cross-check manifest

    This function is safe to call even when no data has been downloaded yet
    — it returns a graceful result rather than raising.

    Returns list of ValidationResult objects.
    """
    MAX_EVENTS_SAMPLE = 20
    MAX_LINEUPS_SAMPLE = 20

    results: list[ValidationResult] = []

    # 1 — competitions.json
    comp_result = validate_competitions_file(raw_dir)
    results.append(comp_result)
    logger.info(
        "validation.file",
        dataset="competitions.json",
        valid=comp_result.valid_rows,
        invalid=comp_result.invalid_rows,
        errors=len(comp_result.errors),
    )

    # 2 — matches files
    matches_dir = raw_dir / "matches"
    if matches_dir.exists():
        match_files = sorted(matches_dir.rglob("*.json"))
        logger.info("validation.matches.start", file_count=len(match_files))
        for mf in match_files:
            # Path is matches/{comp_id}/{season_id}.json
            try:
                comp_id = int(mf.parent.name)
                season_id = int(mf.stem)
            except ValueError:
                logger.warning("validation.matches.unexpected_path", path=str(mf))
                continue
            result = validate_matches_file(mf, comp_id, season_id)
            results.append(result)
    else:
        results.append(
            ValidationResult(
                dataset="matches/ (directory)",
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                warnings=["matches/ directory not found — run `make data` first"],
            )
        )

    # 3 — events (sample)
    events_dir = raw_dir / "events"
    if events_dir.exists():
        event_files = sorted(events_dir.glob("*.json"))
        logger.info(
            "validation.events.start",
            total_files=len(event_files),
            sampling=min(MAX_EVENTS_SAMPLE, len(event_files)),
        )
        for ef in event_files[:MAX_EVENTS_SAMPLE]:
            try:
                match_id = int(ef.stem)
            except ValueError:
                logger.warning("validation.events.unexpected_filename", path=str(ef))
                continue
            result = validate_events_file(ef, match_id)
            results.append(result)

        if len(event_files) > MAX_EVENTS_SAMPLE:
            results.append(
                ValidationResult(
                    dataset=f"events/ (remaining {len(event_files) - MAX_EVENTS_SAMPLE} files)",
                    total_rows=len(event_files) - MAX_EVENTS_SAMPLE,
                    valid_rows=len(event_files) - MAX_EVENTS_SAMPLE,
                    invalid_rows=0,
                    warnings=[
                        f"Sampled {MAX_EVENTS_SAMPLE}/{len(event_files)} event files"
                    ],
                )
            )
    else:
        results.append(
            ValidationResult(
                dataset="events/ (directory)",
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                warnings=["events/ directory not found — run `make data` first"],
            )
        )

    # 4 — lineups (sample)
    lineups_dir = raw_dir / "lineups"
    if lineups_dir.exists():
        lineup_files = sorted(lineups_dir.glob("*.json"))
        logger.info(
            "validation.lineups.start",
            total_files=len(lineup_files),
            sampling=min(MAX_LINEUPS_SAMPLE, len(lineup_files)),
        )
        for lf in lineup_files[:MAX_LINEUPS_SAMPLE]:
            try:
                match_id = int(lf.stem)
            except ValueError:
                logger.warning("validation.lineups.unexpected_filename", path=str(lf))
                continue
            result = validate_lineups_file(lf, match_id)
            results.append(result)
    else:
        results.append(
            ValidationResult(
                dataset="lineups/ (directory)",
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                warnings=["lineups/ directory not found — run `make data` first"],
            )
        )

    # 5 — manifest cross-check
    manifest_result = validate_manifest_consistency(raw_dir)
    results.append(manifest_result)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Report generator (shared by Layer A and Layer B)
# ─────────────────────────────────────────────────────────────────────────────


def generate_validation_report(results: list[ValidationResult]) -> str:
    """
    Generate a human-readable validation report from a list of results.

    Returns the report as a multi-line string.
    """
    lines: list[str] = [
        "═" * 64,
        "  Athena — Data Validation Report",
        "═" * 64,
        "",
    ]

    total_datasets = len(results)
    total_valid = sum(r.valid_rows for r in results)
    total_invalid = sum(r.invalid_rows for r in results)
    datasets_clean = sum(1 for r in results if r.is_valid)
    total_errors = sum(len(r.errors) for r in results)
    total_warnings = sum(len(r.warnings) for r in results)

    lines += [
        f"  Datasets validated : {total_datasets}",
        f"  Datasets clean     : {datasets_clean} / {total_datasets}",
        f"  Total valid rows   : {total_valid:,}",
        f"  Total invalid rows : {total_invalid:,}",
        f"  Total errors       : {total_errors}",
        f"  Total warnings     : {total_warnings}",
        "",
    ]

    for result in results:
        status = "✓ PASS" if result.is_valid else "✗ FAIL"
        lines += [
            "─" * 64,
            f"  {status}  {result.dataset}",
            f"  Total   : {result.total_rows:,}",
            f"  Valid   : {result.valid_rows:,} ({result.validity_pct}%)",
            f"  Invalid : {result.invalid_rows:,}",
        ]
        if result.errors:
            lines.append("  Errors  :")
            for e in result.errors[:10]:  # cap at 10 per dataset
                lines.append(f"    ✗ {e}")
            if len(result.errors) > 10:
                lines.append(f"    … and {len(result.errors) - 10} more errors")
        if result.warnings:
            lines.append("  Warnings:")
            for w in result.warnings[:5]:  # cap at 5 per dataset
                lines.append(f"    ⚠ {w}")
            if len(result.warnings) > 5:
                lines.append(f"    … and {len(result.warnings) - 5} more warnings")
        lines.append("")

    lines += ["═" * 64]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Layer B — DataFrame validators (used by ETL pipeline in Sprint 1.3)
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


def validate_competitions(df: pd.DataFrame) -> ValidationResult:
    """Validate the competitions DataFrame (ETL layer)."""
    result = ValidationResult(
        dataset="competitions",
        total_rows=len(df),
        valid_rows=0,
        invalid_rows=0,
    )

    missing_cols = [c for c in REQUIRED_COMPETITION_COLS if c not in df.columns]
    if missing_cols:
        result.errors.append(f"Missing columns: {missing_cols}")
        result.invalid_rows = len(df)
        return result

    null_ids = df["competition_id"].isna() | df["season_id"].isna()
    null_count = int(null_ids.sum())
    if null_count:
        result.errors.append(f"{null_count} rows with null competition_id or season_id")
        result.invalid_rows += null_count

    duplicates = int(df.duplicated(subset=["competition_id", "season_id"]).sum())
    if duplicates:
        result.warnings.append(
            f"{duplicates} duplicate (competition_id, season_id) rows"
        )

    result.valid_rows = max(0, len(df) - result.invalid_rows)
    return result


def validate_matches(
    df: pd.DataFrame, source_label: str = "matches"
) -> ValidationResult:
    """Validate a matches DataFrame (ETL layer)."""
    result = ValidationResult(
        dataset=source_label,
        total_rows=len(df),
        valid_rows=0,
        invalid_rows=0,
    )

    missing_cols = [c for c in REQUIRED_MATCH_COLS if c not in df.columns]
    if missing_cols:
        result.warnings.append(
            f"Missing columns (may use different schema): {missing_cols}"
        )

    if "match_id" in df.columns:
        null_match_ids = int(df["match_id"].isna().sum())
        if null_match_ids:
            result.errors.append(f"{null_match_ids} rows with null match_id")
            result.invalid_rows += null_match_ids

        duplicates = int(df.duplicated(subset=["match_id"]).sum())
        if duplicates:
            result.errors.append(f"{duplicates} duplicate match_ids")
            result.invalid_rows += duplicates

    for col in ["home_score", "away_score"]:
        if col in df.columns:
            negative = int((df[col] < 0).sum())
            if negative:
                result.errors.append(f"{negative} rows with negative {col}")
                result.invalid_rows += negative

    result.valid_rows = max(0, len(df) - result.invalid_rows)
    return result


def validate_events(df: pd.DataFrame, match_id: int) -> ValidationResult:
    """Validate events DataFrame for a single match (ETL layer)."""
    result = ValidationResult(
        dataset=f"events_match_{match_id}",
        total_rows=len(df),
        valid_rows=0,
        invalid_rows=0,
    )

    if df.empty:
        result.errors.append("Empty events DataFrame")
        return result

    missing_cols = [c for c in REQUIRED_EVENT_COLS if c not in df.columns]
    if missing_cols:
        result.warnings.append(f"Missing columns (schema may differ): {missing_cols}")

    if "minute" in df.columns:
        negative_minutes = int((df["minute"] < 0).sum())
        if negative_minutes:
            result.errors.append(f"{negative_minutes} events with negative minute")
            result.invalid_rows += negative_minutes

        impossible_minutes = int((df["minute"] > 150).sum())
        if impossible_minutes:
            result.warnings.append(
                f"{impossible_minutes} events with minute > 150 (extra time?)"
            )

    if "type" in df.columns:
        null_types = int(df["type"].isna().sum())
        if null_types:
            result.errors.append(f"{null_types} events with null type")
            result.invalid_rows += null_types

    result.valid_rows = max(0, len(df) - result.invalid_rows)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Run validation entry point
# ─────────────────────────────────────────────────────────────────────────────


def run_validation(raw_dir: Path = RAW_DIR) -> list[ValidationResult]:
    """
    Run the full Layer A validation against data/raw/.

    Validates competitions.json, all match files, sampled event and lineup
    files, and checks manifest consistency.

    Returns list of ValidationResult objects and prints the report.
    """
    logger.info("validation.start", raw_dir=str(raw_dir))

    if not raw_dir.exists():
        logger.warning(
            "validation.no_dir",
            message="data/raw/ does not exist. Run `make data` first.",
        )
        no_data = ValidationResult(
            dataset="data/raw/ (directory)",
            total_rows=0,
            valid_rows=0,
            invalid_rows=0,
            warnings=["data/raw/ directory not found. Run `make data` first."],
        )
        report = generate_validation_report([no_data])
        print(report)
        return [no_data]

    results = validate_raw_directory(raw_dir)
    report = generate_validation_report(results)

    # Write to validation log
    try:
        validation_logger.info("report", content=report)
    except Exception:
        pass  # logging failure must never abort validation

    # Write via sys.stdout.buffer as UTF-8 to avoid UnicodeEncodeError on
    # Windows terminals that default to cp1252 (which lacks box-drawing chars).
    try:
        sys.stdout.buffer.write((report + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    except AttributeError:
        # Fallback for environments where stdout has no .buffer (e.g. pytest capture)
        print(report)

    clean = all(r.is_valid for r in results)
    logger.info(
        "validation.complete",
        datasets=len(results),
        all_clean=clean,
        errors=sum(len(r.errors) for r in results),
    )
    return results


def main() -> None:
    run_validation()


if __name__ == "__main__":
    main()
