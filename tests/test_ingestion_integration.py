"""
tests/test_ingestion_integration.py — Integration tests for Sprint 1.1

Tests the following without network access or real data:
  - ManifestManager: load / save / round-trip / idempotency helpers
  - DownloadManifest: record / query / serialisation
  - StatsBombDownloader: file-save logic (HTTP mocked), idempotency, skip
  - File-level validators: competitions, matches, events, lineups JSON
  - validate_manifest_consistency: cross-reference checks
  - validate_raw_directory: full directory scan with synthetic files

All tests use pytest's tmp_path fixture — no files are written to data/raw/.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.ingestion.load_data import DownloadSummary, StatsBombDownloader
from backend.ingestion.manifest import (
    DownloadManifest,
    ManifestManager,
)
from backend.ingestion.validator import (
    validate_competitions_file,
    validate_events_file,
    validate_lineups_file,
    validate_manifest_consistency,
    validate_matches_file,
    validate_raw_directory,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — minimal valid StatsBomb-format JSON
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def competitions_json() -> list[dict]:
    return [
        {
            "competition_id": 11,
            "competition_name": "La Liga",
            "country_name": "Spain",
            "season_id": 90,
            "season_name": "2020/2021",
            "competition_gender": "male",
            "competition_youth": False,
            "competition_international": False,
            "match_available": "2021-08-23T09:00:00.000000",
        },
        {
            "competition_id": 16,
            "competition_name": "Champions League",
            "country_name": "Europe",
            "season_id": 4,
            "season_name": "2018/2019",
            "competition_gender": "male",
            "competition_youth": False,
            "competition_international": True,
            "match_available": "2020-01-01T00:00:00.000000",
        },
    ]


@pytest.fixture
def matches_json() -> list[dict]:
    return [
        {
            "match_id": 3772064,
            "match_date": "2020-09-27",
            "kick_off": "16:00:00.000",
            "competition": {"competition_id": 11, "competition_name": "La Liga"},
            "season": {"season_id": 90, "season_name": "2020/2021"},
            "home_team": {"home_team_id": 217, "home_team_name": "Barcelona"},
            "away_team": {"away_team_id": 218, "away_team_name": "Villarreal"},
            "home_score": 4,
            "away_score": 0,
            "match_status": "available",
        },
        {
            "match_id": 3772065,
            "match_date": "2020-09-28",
            "kick_off": "20:00:00.000",
            "competition": {"competition_id": 11, "competition_name": "La Liga"},
            "season": {"season_id": 90, "season_name": "2020/2021"},
            "home_team": {"home_team_id": 220, "home_team_name": "Real Madrid"},
            "away_team": {"away_team_id": 221, "away_team_name": "Getafe"},
            "home_score": 2,
            "away_score": 0,
            "match_status": "available",
        },
    ]


@pytest.fixture
def events_json() -> list[dict]:
    """Minimal valid events for match 3772064."""
    return [
        {
            "id": "a1b2c3d4",
            "index": 1,
            "type": {"id": 35, "name": "Starting XI"},
            "minute": 0,
            "second": 0,
            "team": {"id": 217, "name": "Barcelona"},
            "player": None,
            "possession": 1,
            "possession_team": {"id": 217, "name": "Barcelona"},
        },
        {
            "id": "e5f6g7h8",
            "index": 2,
            "type": {"id": 30, "name": "Pass"},
            "minute": 1,
            "second": 14,
            "team": {"id": 217, "name": "Barcelona"},
            "player": {"id": 5503, "name": "Lionel Andrés Messi Cuccittini"},
            "possession": 2,
            "possession_team": {"id": 217, "name": "Barcelona"},
        },
    ]


@pytest.fixture
def lineups_json() -> list[dict]:
    """Minimal valid lineups for match 3772064."""
    return [
        {
            "team_id": 217,
            "team_name": "Barcelona",
            "lineup": [
                {
                    "player_id": 5503,
                    "player_name": "Lionel Andrés Messi Cuccittini",
                    "player_nickname": "Messi",
                    "jersey_number": 10,
                    "country": {"id": 11, "name": "Argentina"},
                }
            ],
        },
        {
            "team_id": 218,
            "team_name": "Villarreal",
            "lineup": [
                {
                    "player_id": 6789,
                    "player_name": "Gerard Moreno",
                    "player_nickname": None,
                    "jersey_number": 7,
                    "country": {"id": 214, "name": "Spain"},
                }
            ],
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Tests — DownloadManifest
# ─────────────────────────────────────────────────────────────────────────────


class TestDownloadManifest:
    """Tests for DownloadManifest dataclass."""

    def test_fresh_manifest_has_zero_counts(self) -> None:
        m = DownloadManifest()
        assert m.total_matches == 0
        assert m.total_events == 0
        assert m.total_lineups == 0

    def test_record_competition_adds_entry(self) -> None:
        m = DownloadManifest()
        m.record_competition(11, "La Liga", 90, "2020/2021", [3772064, 3772065])
        assert len(m.competitions) == 1
        assert m.total_matches == 2

    def test_record_competition_replaces_existing(self) -> None:
        """Re-recording the same competition/season replaces the old record."""
        m = DownloadManifest()
        m.record_competition(11, "La Liga", 90, "2020/2021", [1000, 2000])
        m.record_competition(11, "La Liga", 90, "2020/2021", [3000])  # replace
        assert len(m.competitions) == 1
        assert m.total_matches == 1  # only [3000]

    def test_record_events_adds_to_list(self) -> None:
        m = DownloadManifest()
        m.record_events(3772064)
        m.record_events(3772065)
        assert 3772064 in m.events_downloaded
        assert 3772065 in m.events_downloaded
        assert m.total_events == 2

    def test_record_events_idempotent(self) -> None:
        """Recording the same match_id twice does not duplicate it."""
        m = DownloadManifest()
        m.record_events(3772064)
        m.record_events(3772064)
        assert m.total_events == 1

    def test_has_matches_returns_true_when_recorded(self) -> None:
        m = DownloadManifest()
        m.record_competition(11, "La Liga", 90, "2020/2021", [3772064])
        assert m.has_matches(11, 90) is True

    def test_has_matches_returns_false_for_unrecorded(self) -> None:
        m = DownloadManifest()
        assert m.has_matches(11, 90) is False

    def test_has_events_returns_false_when_empty(self) -> None:
        m = DownloadManifest()
        assert m.has_events(3772064) is False

    def test_has_events_returns_true_when_recorded(self) -> None:
        m = DownloadManifest()
        m.record_events(3772064)
        assert m.has_events(3772064) is True

    def test_all_match_ids_aggregates_across_competitions(self) -> None:
        m = DownloadManifest()
        m.record_competition(11, "La Liga", 90, "2020/2021", [1, 2])
        m.record_competition(16, "UCL", 4, "2018/2019", [3, 4])
        ids = m.all_match_ids()
        assert sorted(ids) == [1, 2, 3, 4]

    def test_competition_seasons_returns_pairs(self) -> None:
        m = DownloadManifest()
        m.record_competition(11, "La Liga", 90, "2020/2021", [])
        m.record_competition(16, "UCL", 4, "2018/2019", [])
        pairs = m.competition_seasons()
        assert (11, 90) in pairs
        assert (16, 4) in pairs

    def test_serialisation_round_trip(self) -> None:
        """to_dict() → from_dict() must reproduce the same manifest."""
        m = DownloadManifest(mode="sample")
        m.record_competition(11, "La Liga", 90, "2020/2021", [3772064])
        m.record_events(3772064)
        m.record_lineups(3772064)

        restored = DownloadManifest.from_dict(m.to_dict())
        assert restored.mode == "sample"
        assert restored.total_matches == 1
        assert restored.total_events == 1
        assert restored.total_lineups == 1
        assert restored.has_events(3772064) is True
        assert restored.competitions[0].competition_name == "La Liga"


# ─────────────────────────────────────────────────────────────────────────────
# Tests — ManifestManager
# ─────────────────────────────────────────────────────────────────────────────


class TestManifestManager:
    """Tests for ManifestManager persistence layer."""

    def test_load_returns_empty_manifest_when_no_file(self, tmp_path: Path) -> None:
        manager = ManifestManager(tmp_path)
        manifest = manager.load()
        assert isinstance(manifest, DownloadManifest)
        assert manifest.total_matches == 0
        assert manifest.total_events == 0

    def test_save_creates_manifest_file(self, tmp_path: Path) -> None:
        manager = ManifestManager(tmp_path)
        manifest = DownloadManifest(mode="sample")
        manager.save(manifest)
        assert (tmp_path / "manifest.json").exists()

    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        manager = ManifestManager(tmp_path)
        manifest = DownloadManifest(mode="competition")
        manifest.record_competition(11, "La Liga", 90, "2020/2021", [3772064])
        manifest.record_events(3772064)
        manifest.record_lineups(3772064)
        manager.save(manifest)

        loaded = manager.load()
        assert loaded.mode == "competition"
        assert loaded.has_events(3772064) is True
        assert loaded.has_lineups(3772064) is True
        assert loaded.total_matches == 1

    def test_load_returns_empty_on_corrupted_file(self, tmp_path: Path) -> None:
        """A corrupted manifest.json must not raise — returns empty manifest."""
        path = tmp_path / "manifest.json"
        path.write_text("{ this is not valid json !!!", encoding="utf-8")
        manager = ManifestManager(tmp_path)
        manifest = manager.load()
        assert isinstance(manifest, DownloadManifest)
        assert manifest.total_matches == 0

    def test_exists_returns_false_before_save(self, tmp_path: Path) -> None:
        manager = ManifestManager(tmp_path)
        assert manager.exists() is False

    def test_exists_returns_true_after_save(self, tmp_path: Path) -> None:
        manager = ManifestManager(tmp_path)
        manager.save(DownloadManifest())
        assert manager.exists() is True

    def test_atomic_save_no_temp_file_left_over(self, tmp_path: Path) -> None:
        """The .json.tmp temp file must be removed after successful save."""
        manager = ManifestManager(tmp_path)
        manager.save(DownloadManifest())
        assert not (tmp_path / "manifest.json.tmp").exists()


# ─────────────────────────────────────────────────────────────────────────────
# Tests — StatsBombDownloader file operations (HTTP mocked)
# ─────────────────────────────────────────────────────────────────────────────


class TestStatsBombDownloaderFileOps:
    """
    Test StatsBombDownloader without network access.

    _fetch_json is patched to return fixture data immediately.
    """

    def _make_downloader(
        self, tmp_path: Path, force: bool = False
    ) -> StatsBombDownloader:
        return StatsBombDownloader(raw_dir=tmp_path, delay_s=0.0, force=force)

    def test_download_competitions_saves_json(
        self, tmp_path: Path, competitions_json: list[dict]
    ) -> None:
        downloader = self._make_downloader(tmp_path)
        with patch.object(downloader, "_fetch_json", return_value=competitions_json):
            data, was_new = downloader.download_competitions()
        assert was_new is True
        assert (tmp_path / "competitions.json").exists()
        assert len(data) == 2

    def test_download_competitions_skips_if_exists(
        self, tmp_path: Path, competitions_json: list[dict]
    ) -> None:
        # Pre-create the file
        dest = tmp_path / "competitions.json"
        dest.write_text(json.dumps(competitions_json), encoding="utf-8")
        downloader = self._make_downloader(tmp_path)

        with patch.object(downloader, "_fetch_json", return_value=[]) as mock_fetch:
            data, was_new = downloader.download_competitions()

        mock_fetch.assert_not_called()  # must NOT have made a network request
        assert was_new is False
        assert len(data) == 2  # reads from existing file

    def test_download_competitions_force_overwrites(
        self, tmp_path: Path, competitions_json: list[dict]
    ) -> None:
        dest = tmp_path / "competitions.json"
        dest.write_text(json.dumps([{"stale": True}]), encoding="utf-8")
        downloader = self._make_downloader(tmp_path, force=True)

        with patch.object(downloader, "_fetch_json", return_value=competitions_json):
            data, was_new = downloader.download_competitions()

        assert was_new is True
        assert len(data) == 2

    def test_download_matches_creates_nested_dirs(
        self, tmp_path: Path, matches_json: list[dict]
    ) -> None:
        downloader = self._make_downloader(tmp_path)
        manifest = DownloadManifest()
        with patch.object(downloader, "_fetch_json", return_value=matches_json):
            data, was_new = downloader.download_matches(11, 90, manifest)
        assert was_new is True
        assert (tmp_path / "matches" / "11" / "90.json").exists()
        assert len(data) == 2

    def test_download_matches_skips_if_in_manifest(
        self, tmp_path: Path, matches_json: list[dict]
    ) -> None:
        dest = tmp_path / "matches" / "11" / "90.json"
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps(matches_json), encoding="utf-8")

        manifest = DownloadManifest()
        manifest.record_competition(11, "La Liga", 90, "2020/2021", [3772064])

        downloader = self._make_downloader(tmp_path)
        with patch.object(downloader, "_fetch_json", return_value=[]) as mock_fetch:
            data, was_new = downloader.download_matches(11, 90, manifest)

        mock_fetch.assert_not_called()
        assert was_new is False

    def test_download_events_saves_to_correct_path(
        self, tmp_path: Path, events_json: list[dict]
    ) -> None:
        downloader = self._make_downloader(tmp_path)
        manifest = DownloadManifest()
        with patch.object(downloader, "_fetch_json", return_value=events_json):
            result = downloader.download_events(3772064, manifest)
        assert result is True
        assert (tmp_path / "events" / "3772064.json").exists()

    def test_download_events_skips_if_in_manifest(
        self, tmp_path: Path, events_json: list[dict]
    ) -> None:
        dest = tmp_path / "events" / "3772064.json"
        dest.parent.mkdir(parents=True)
        dest.write_text(json.dumps(events_json), encoding="utf-8")

        manifest = DownloadManifest()
        manifest.record_events(3772064)

        downloader = self._make_downloader(tmp_path)
        with patch.object(downloader, "_fetch_json", return_value=[]) as mock_fetch:
            result = downloader.download_events(3772064, manifest)

        mock_fetch.assert_not_called()
        assert result is False

    def test_download_lineups_saves_to_correct_path(
        self, tmp_path: Path, lineups_json: list[dict]
    ) -> None:
        downloader = self._make_downloader(tmp_path)
        manifest = DownloadManifest()
        with patch.object(downloader, "_fetch_json", return_value=lineups_json):
            result = downloader.download_lineups(3772064, manifest)
        assert result is True
        assert (tmp_path / "lineups" / "3772064.json").exists()

    def test_saved_json_is_valid_and_parseable(
        self, tmp_path: Path, competitions_json: list[dict]
    ) -> None:
        downloader = self._make_downloader(tmp_path)
        with patch.object(downloader, "_fetch_json", return_value=competitions_json):
            downloader.download_competitions()

        with open(tmp_path / "competitions.json", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 2
        assert data[0]["competition_id"] == 11


# ─────────────────────────────────────────────────────────────────────────────
# Tests — DownloadSummary
# ─────────────────────────────────────────────────────────────────────────────


class TestDownloadSummary:
    def test_total_downloaded_aggregates_all_types(self) -> None:
        s = DownloadSummary(mode="sample")
        s.downloaded_competitions = 1
        s.downloaded_matches = 3
        s.downloaded_events = 3
        s.downloaded_lineups = 3
        assert s.total_downloaded == 10

    def test_total_failed_aggregates_failures(self) -> None:
        s = DownloadSummary(mode="sample")
        s.failed_events = 2
        s.failed_lineups = 1
        assert s.total_failed == 3

    def test_report_lines_returns_list_of_strings(self) -> None:
        s = DownloadSummary(mode="sample")
        lines = s.report_lines()
        assert isinstance(lines, list)
        assert all(isinstance(line, str) for line in lines)
        assert any("sample" in line for line in lines)


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_competitions_file
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateCompetitionsFile:
    def test_valid_competitions_passes(
        self, tmp_path: Path, competitions_json: list[dict]
    ) -> None:
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps(competitions_json), encoding="utf-8")
        result = validate_competitions_file(tmp_path)
        assert result.is_valid, f"Expected valid but got errors: {result.errors}"
        assert result.total_rows == 2

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        result = validate_competitions_file(tmp_path)
        assert not result.is_valid
        assert any("not found" in e for e in result.errors)

    def test_invalid_json_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "competitions.json"
        path.write_text("{ invalid json !!!", encoding="utf-8")
        result = validate_competitions_file(tmp_path)
        assert not result.is_valid
        assert any("JSON parse error" in e for e in result.errors)

    def test_missing_required_key_fails(self, tmp_path: Path) -> None:
        data = [{"competition_id": 11, "season_id": 90}]  # missing names
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = validate_competitions_file(tmp_path)
        assert not result.is_valid
        assert any("missing keys" in e for e in result.errors)

    def test_empty_list_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "competitions.json"
        path.write_text("[]", encoding="utf-8")
        result = validate_competitions_file(tmp_path)
        assert not result.is_valid

    def test_not_a_list_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "competitions.json"
        path.write_text('{"competition_id": 11}', encoding="utf-8")
        result = validate_competitions_file(tmp_path)
        assert not result.is_valid

    def test_duplicate_pair_produces_warning(
        self, tmp_path: Path, competitions_json: list[dict]
    ) -> None:
        # Add duplicate of first entry
        data = competitions_json + [competitions_json[0]]
        path = tmp_path / "competitions.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = validate_competitions_file(tmp_path)
        assert any("Duplicate" in w for w in result.warnings)


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_matches_file
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateMatchesFile:
    def _write_matches(self, tmp_path: Path, data: list[dict]) -> Path:
        path = tmp_path / "matches" / "11" / "90.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_matches_passes(
        self, tmp_path: Path, matches_json: list[dict]
    ) -> None:
        path = self._write_matches(tmp_path, matches_json)
        result = validate_matches_file(path, 11, 90)
        assert result.is_valid

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "matches" / "11" / "90.json"
        result = validate_matches_file(path, 11, 90)
        assert not result.is_valid
        assert any("not found" in e for e in result.errors)

    def test_negative_score_fails(self, tmp_path: Path) -> None:
        data = [
            {
                "match_id": 1001,
                "match_date": "2020-09-27",
                "home_team": {},
                "away_team": {},
                "home_score": -1,
                "away_score": 2,
            }
        ]
        path = self._write_matches(tmp_path, data)
        result = validate_matches_file(path, 11, 90)
        assert not result.is_valid
        assert any("negative" in e for e in result.errors)

    def test_duplicate_match_id_fails(
        self, tmp_path: Path, matches_json: list[dict]
    ) -> None:
        # Duplicate first match
        data = matches_json + [matches_json[0]]
        path = self._write_matches(tmp_path, data)
        result = validate_matches_file(path, 11, 90)
        assert not result.is_valid
        assert any("Duplicate match_id" in e for e in result.errors)

    def test_missing_required_key_fails(self, tmp_path: Path) -> None:
        data = [{"match_id": 1001, "home_score": 1, "away_score": 0}]  # missing keys
        path = self._write_matches(tmp_path, data)
        result = validate_matches_file(path, 11, 90)
        assert not result.is_valid


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_events_file
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateEventsFile:
    def _write_events(
        self, tmp_path: Path, data: list[dict], match_id: int = 3772064
    ) -> Path:
        path = tmp_path / "events" / f"{match_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_events_passes(self, tmp_path: Path, events_json: list[dict]) -> None:
        path = self._write_events(tmp_path, events_json)
        result = validate_events_file(path, 3772064)
        assert result.is_valid

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "events" / "9999.json"
        result = validate_events_file(path, 9999)
        assert not result.is_valid

    def test_empty_events_fails(self, tmp_path: Path) -> None:
        path = self._write_events(tmp_path, [])
        result = validate_events_file(path, 3772064)
        assert not result.is_valid

    def test_negative_minute_fails(
        self, tmp_path: Path, events_json: list[dict]
    ) -> None:
        bad_event = dict(events_json[0])
        bad_event["minute"] = -1
        path = self._write_events(tmp_path, [bad_event])
        result = validate_events_file(path, 3772064)
        assert not result.is_valid
        assert any("negative" in e for e in result.errors)

    def test_high_minute_warns_not_fails(
        self, tmp_path: Path, events_json: list[dict]
    ) -> None:
        high_event = dict(events_json[0])
        high_event["minute"] = 151
        path = self._write_events(tmp_path, [high_event])
        result = validate_events_file(path, 3772064)
        # Minute=151 is a warning not an error
        assert any("151" in w or "150" in w for w in result.warnings)

    def test_duplicate_event_id_fails(
        self, tmp_path: Path, events_json: list[dict]
    ) -> None:
        data = [events_json[0], events_json[0]]  # same ID twice
        path = self._write_events(tmp_path, data)
        result = validate_events_file(path, 3772064)
        assert not result.is_valid
        assert any("Duplicate event id" in e for e in result.errors)

    def test_missing_required_event_key_fails(self, tmp_path: Path) -> None:
        data = [{"id": "abc", "minute": 5}]  # missing index, type, second
        path = self._write_events(tmp_path, data)
        result = validate_events_file(path, 3772064)
        assert not result.is_valid


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_lineups_file
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateLineupsFile:
    def _write_lineups(
        self, tmp_path: Path, data: list[dict], match_id: int = 3772064
    ) -> Path:
        path = tmp_path / "lineups" / f"{match_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_lineups_passes(
        self, tmp_path: Path, lineups_json: list[dict]
    ) -> None:
        path = self._write_lineups(tmp_path, lineups_json)
        result = validate_lineups_file(path, 3772064)
        assert result.is_valid

    def test_missing_file_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "lineups" / "9999.json"
        result = validate_lineups_file(path, 9999)
        assert not result.is_valid

    def test_not_a_list_lineup_key_fails(
        self, tmp_path: Path, lineups_json: list[dict]
    ) -> None:
        bad = [
            {
                "team_id": 217,
                "team_name": "Barcelona",
                "lineup": "not-a-list",  # ← wrong type
            },
            lineups_json[1],
        ]
        path = self._write_lineups(tmp_path, bad)
        result = validate_lineups_file(path, 3772064)
        assert not result.is_valid

    def test_missing_team_id_fails(
        self, tmp_path: Path, lineups_json: list[dict]
    ) -> None:
        bad = [
            {"team_name": "Barcelona", "lineup": []},  # missing team_id
            lineups_json[1],
        ]
        path = self._write_lineups(tmp_path, bad)
        result = validate_lineups_file(path, 3772064)
        assert not result.is_valid


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_manifest_consistency
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateManifestConsistency:
    def _write_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_warns_when_no_manifest(self, tmp_path: Path) -> None:
        result = validate_manifest_consistency(tmp_path)
        assert any("manifest.json not found" in w for w in result.warnings)

    def test_passes_when_all_files_present(
        self,
        tmp_path: Path,
        events_json: list[dict],
        lineups_json: list[dict],
        matches_json: list[dict],
    ) -> None:
        # Create files
        self._write_json(tmp_path / "matches" / "11" / "90.json", matches_json)
        self._write_json(tmp_path / "events" / "3772064.json", events_json)
        self._write_json(tmp_path / "lineups" / "3772064.json", lineups_json)

        # Create manifest recording the same files
        manager = ManifestManager(tmp_path)
        manifest = DownloadManifest(mode="sample")
        manifest.record_competition(11, "La Liga", 90, "2020/2021", [3772064])
        manifest.record_events(3772064)
        manifest.record_lineups(3772064)
        manager.save(manifest)

        result = validate_manifest_consistency(tmp_path)
        assert result.is_valid, f"Expected valid but got: {result.errors}"

    def test_fails_when_events_file_missing(
        self,
        tmp_path: Path,
        matches_json: list[dict],
        lineups_json: list[dict],
    ) -> None:
        self._write_json(tmp_path / "matches" / "11" / "90.json", matches_json)
        # events file intentionally NOT created
        self._write_json(tmp_path / "lineups" / "3772064.json", lineups_json)

        manager = ManifestManager(tmp_path)
        manifest = DownloadManifest(mode="sample")
        manifest.record_competition(11, "La Liga", 90, "2020/2021", [3772064])
        manifest.record_events(3772064)  # recorded but file missing
        manifest.record_lineups(3772064)
        manager.save(manifest)

        result = validate_manifest_consistency(tmp_path)
        assert not result.is_valid
        assert any("events/3772064.json" in e for e in result.errors)

    def test_fails_when_matches_file_missing(self, tmp_path: Path) -> None:
        manager = ManifestManager(tmp_path)
        manifest = DownloadManifest(mode="sample")
        manifest.record_competition(11, "La Liga", 90, "2020/2021", [])
        # matches file NOT created
        manager.save(manifest)

        result = validate_manifest_consistency(tmp_path)
        assert not result.is_valid
        assert any("matches/11/90.json" in e for e in result.errors)


# ─────────────────────────────────────────────────────────────────────────────
# Tests — validate_raw_directory (integration)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateRawDirectory:
    """Integration test: validate_raw_directory with a fully synthetic dataset."""

    def _write_json(self, path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_returns_no_data_warning_for_empty_directory(self, tmp_path: Path) -> None:
        results = validate_raw_directory(tmp_path)
        # Should have at least one result
        assert len(results) > 0
        # competitions.json not found → error in first result
        assert any("not found" in e for r in results for e in r.errors)

    def test_full_valid_dataset_passes(
        self,
        tmp_path: Path,
        competitions_json: list[dict],
        matches_json: list[dict],
        events_json: list[dict],
        lineups_json: list[dict],
    ) -> None:
        # Write all files
        self._write_json(tmp_path / "competitions.json", competitions_json)
        self._write_json(tmp_path / "matches" / "11" / "90.json", matches_json)
        self._write_json(tmp_path / "events" / "3772064.json", events_json)
        self._write_json(tmp_path / "lineups" / "3772064.json", lineups_json)

        # Write manifest
        manager = ManifestManager(tmp_path)
        manifest = DownloadManifest(mode="sample")
        manifest.record_competition(11, "La Liga", 90, "2020/2021", [3772064])
        manifest.record_events(3772064)
        manifest.record_lineups(3772064)
        manager.save(manifest)

        results = validate_raw_directory(tmp_path)
        errors = [e for r in results for e in r.errors]
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_results_include_all_dataset_types(
        self,
        tmp_path: Path,
        competitions_json: list[dict],
        matches_json: list[dict],
        events_json: list[dict],
        lineups_json: list[dict],
    ) -> None:
        self._write_json(tmp_path / "competitions.json", competitions_json)
        self._write_json(tmp_path / "matches" / "11" / "90.json", matches_json)
        self._write_json(tmp_path / "events" / "3772064.json", events_json)
        self._write_json(tmp_path / "lineups" / "3772064.json", lineups_json)

        results = validate_raw_directory(tmp_path)
        dataset_names = [r.dataset for r in results]
        assert any("competitions.json" in n for n in dataset_names)
        assert any("matches" in n for n in dataset_names)
        assert any("events" in n for n in dataset_names)
        assert any("lineups" in n for n in dataset_names)
