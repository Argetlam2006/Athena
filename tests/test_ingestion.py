"""
tests/test_ingestion.py — Unit tests for the data ingestion layer

Tests are deterministic and do not require network access or full data.
They validate the correctness of validator logic using synthetic DataFrames.

Run with:
    pytest tests/test_ingestion.py -v
    make test-unit
"""

from __future__ import annotations

import pandas as pd
import pytest

from backend.ingestion.validator import (
    generate_validation_report,
    validate_competitions,
    validate_events,
    validate_matches,
)
from shared.schemas import ValidationResult

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — minimal valid DataFrames
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def valid_competitions_df() -> pd.DataFrame:
    """A well-formed competitions DataFrame."""
    return pd.DataFrame(
        [
            {
                "competition_id": 11,
                "competition_name": "La Liga",
                "country_name": "Spain",
                "season_id": 90,
                "season_name": "2020/2021",
            },
            {
                "competition_id": 16,
                "competition_name": "Champions League",
                "country_name": "Europe",
                "season_id": 4,
                "season_name": "2018/2019",
            },
        ]
    )


@pytest.fixture
def valid_matches_df() -> pd.DataFrame:
    """A well-formed matches DataFrame."""
    return pd.DataFrame(
        [
            {
                "match_id": 1001,
                "competition": {"competition_id": 11, "competition_name": "La Liga"},
                "season": {"season_id": 90, "season_name": "2020/2021"},
                "home_team": {"home_team_name": "Barcelona"},
                "away_team": {"away_team_name": "Real Madrid"},
                "home_score": 2,
                "away_score": 1,
                "match_date": "2020-10-24",
            }
        ]
    )


@pytest.fixture
def valid_events_df() -> pd.DataFrame:
    """A minimal valid events DataFrame for match 1001."""
    return pd.DataFrame(
        [
            {
                "id": "abc123",
                "match_id": 1001,
                "index": 1,
                "type": {"id": 30, "name": "Pass"},
                "player": {"id": 5503, "name": "Lionel Messi"},
                "team": {"id": 217, "name": "Barcelona"},
                "minute": 5,
                "second": 30,
            },
            {
                "id": "def456",
                "match_id": 1001,
                "index": 2,
                "type": {"id": 16, "name": "Shot"},
                "player": {"id": 5503, "name": "Lionel Messi"},
                "team": {"id": 217, "name": "Barcelona"},
                "minute": 12,
                "second": 15,
            },
        ]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_competitions
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateCompetitions:
    """Tests for competition dataset validation."""

    def test_valid_competitions_passes(
        self, valid_competitions_df: pd.DataFrame
    ) -> None:
        """A clean competitions DataFrame should produce no errors."""
        result = validate_competitions(valid_competitions_df)
        assert result.is_valid, f"Expected valid but got errors: {result.errors}"
        assert result.valid_rows == 2
        assert result.invalid_rows == 0

    def test_missing_required_column_fails(self) -> None:
        """A DataFrame missing a required column should fail."""
        df = pd.DataFrame(
            [
                {
                    "competition_name": "La Liga",
                    "season_id": 90,
                    "season_name": "2020/2021",
                }
            ]
        )  # missing competition_id
        result = validate_competitions(df)
        assert not result.is_valid
        assert any("Missing columns" in e for e in result.errors)

    def test_null_competition_id_fails(self) -> None:
        """A row with null competition_id should be flagged as invalid."""
        df = pd.DataFrame(
            [
                {
                    "competition_id": None,
                    "competition_name": "La Liga",
                    "season_id": 90,
                    "season_name": "2020/2021",
                }
            ]
        )
        result = validate_competitions(df)
        assert result.invalid_rows > 0

    def test_duplicate_competition_season_warns(self) -> None:
        """Duplicate (competition_id, season_id) pairs should trigger a warning."""
        df = pd.DataFrame(
            [
                {
                    "competition_id": 11,
                    "competition_name": "La Liga",
                    "season_id": 90,
                    "season_name": "2020/2021",
                },
                {
                    "competition_id": 11,  # duplicate
                    "competition_name": "La Liga",
                    "season_id": 90,
                    "season_name": "2020/2021",
                },
            ]
        )
        result = validate_competitions(df)
        assert any("duplicate" in w.lower() for w in result.warnings)

    def test_empty_dataframe_produces_result(self) -> None:
        """An empty DataFrame should not raise an exception."""
        df = pd.DataFrame(
            columns=["competition_id", "competition_name", "season_id", "season_name"]
        )
        result = validate_competitions(df)
        assert result.total_rows == 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_matches
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateMatches:
    """Tests for match dataset validation."""

    def test_valid_matches_passes(self, valid_matches_df: pd.DataFrame) -> None:
        """A clean matches DataFrame should produce no errors."""
        result = validate_matches(valid_matches_df)
        assert result.is_valid

    def test_negative_score_fails(self) -> None:
        """A match with a negative score should be flagged."""
        df = pd.DataFrame(
            [
                {
                    "match_id": 1001,
                    "home_score": -1,
                    "away_score": 2,
                    "match_date": "2020-10-24",
                }
            ]
        )
        result = validate_matches(df)
        assert not result.is_valid
        assert any("negative" in e.lower() for e in result.errors)

    def test_null_match_id_fails(self) -> None:
        """A match with null match_id should be flagged as invalid."""
        df = pd.DataFrame([{"match_id": None, "home_score": 1, "away_score": 0}])
        result = validate_matches(df)
        assert result.invalid_rows > 0

    def test_duplicate_match_id_fails(self) -> None:
        """Duplicate match_ids should be flagged as errors."""
        df = pd.DataFrame(
            [
                {"match_id": 1001, "home_score": 1, "away_score": 0},
                {"match_id": 1001, "home_score": 1, "away_score": 0},
            ]
        )
        result = validate_matches(df)
        assert not result.is_valid
        assert any("duplicate" in e.lower() for e in result.errors)


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_events
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateEvents:
    """Tests for events dataset validation."""

    def test_valid_events_passes(self, valid_events_df: pd.DataFrame) -> None:
        """A clean events DataFrame should produce no errors."""
        result = validate_events(valid_events_df, match_id=1001)
        assert result.is_valid

    def test_empty_events_fails(self) -> None:
        """An empty events DataFrame should be flagged."""
        result = validate_events(pd.DataFrame(), match_id=9999)
        assert result.total_rows == 0

    def test_negative_minute_fails(self) -> None:
        """Events with negative minutes should be flagged."""
        df = pd.DataFrame(
            [
                {
                    "id": "abc",
                    "match_id": 1001,
                    "index": 1,
                    "type": "Pass",
                    "player": "A",
                    "team": "B",
                    "minute": -1,
                    "second": 0,
                }
            ]
        )
        result = validate_events(df, match_id=1001)
        assert not result.is_valid
        assert any("negative minute" in e.lower() for e in result.errors)

    def test_high_minute_warns_not_fails(self) -> None:
        """Minutes > 150 (deep extra time) should warn, not fail."""
        df = pd.DataFrame(
            [
                {
                    "id": "abc",
                    "match_id": 1001,
                    "index": 1,
                    "type": "Pass",
                    "player": "A",
                    "team": "B",
                    "minute": 151,
                    "second": 0,
                }
            ]
        )
        result = validate_events(df, match_id=1001)
        # Should warn but not add invalid rows
        assert any("151" in w or "150" in w for w in result.warnings)


# ─────────────────────────────────────────────────────────────────────────────
# Tests — ValidationResult schema
# ─────────────────────────────────────────────────────────────────────────────


class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_is_valid_when_no_invalid_rows(self) -> None:
        result = ValidationResult(
            dataset="test", total_rows=100, valid_rows=100, invalid_rows=0
        )
        assert result.is_valid is True

    def test_is_invalid_when_invalid_rows_exist(self) -> None:
        result = ValidationResult(
            dataset="test", total_rows=100, valid_rows=95, invalid_rows=5
        )
        assert result.is_valid is False

    def test_validity_pct_calculated_correctly(self) -> None:
        result = ValidationResult(
            dataset="test", total_rows=200, valid_rows=190, invalid_rows=10
        )
        assert result.validity_pct == 95.0

    def test_validity_pct_zero_rows(self) -> None:
        result = ValidationResult(
            dataset="test", total_rows=0, valid_rows=0, invalid_rows=0
        )
        assert result.validity_pct == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Tests — generate_validation_report
# ─────────────────────────────────────────────────────────────────────────────


class TestGenerateValidationReport:
    """Tests for the report generator."""

    def test_report_is_string(self) -> None:
        results = [
            ValidationResult(
                dataset="competitions", total_rows=10, valid_rows=10, invalid_rows=0
            )
        ]
        report = generate_validation_report(results)
        assert isinstance(report, str)
        assert len(report) > 0

    def test_report_contains_dataset_name(self) -> None:
        results = [
            ValidationResult(
                dataset="test_dataset", total_rows=5, valid_rows=5, invalid_rows=0
            )
        ]
        report = generate_validation_report(results)
        assert "test_dataset" in report

    def test_report_shows_pass_for_clean_data(self) -> None:
        results = [
            ValidationResult(
                dataset="competitions", total_rows=10, valid_rows=10, invalid_rows=0
            )
        ]
        report = generate_validation_report(results)
        assert "PASS" in report

    def test_report_shows_fail_for_invalid_data(self) -> None:
        results = [
            ValidationResult(
                dataset="matches",
                total_rows=10,
                valid_rows=8,
                invalid_rows=2,
                errors=["2 duplicate match_ids"],
            )
        ]
        report = generate_validation_report(results)
        assert "FAIL" in report
