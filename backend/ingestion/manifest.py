"""
backend/ingestion/manifest.py — Download manifest manager

Tracks exactly what has been downloaded to data/raw/, enabling:
  - Idempotent re-runs (skip already-downloaded files)
  - Auditability (who downloaded what, when)
  - Cross-checks in the validation step
  - Progress reporting

Manifest file location: data/raw/manifest.json

Manifest structure:
    {
        "version": "1.0",
        "mode": "sample",
        "created_at": "<iso8601>",
        "updated_at": "<iso8601>",
        "competitions": [
            {
                "competition_id": 11,
                "competition_name": "La Liga",
                "season_id": 90,
                "season_name": "2020/2021",
                "downloaded_at": "<iso8601>",
                "match_ids": [3772064, ...]
            }
        ],
        "events_downloaded": [3772064, ...],
        "lineups_downloaded": [3772064, ...]
    }
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_FILE = "manifest.json"
MANIFEST_VERSION = "1.0"


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CompetitionRecord:
    """One competition+season that has been downloaded."""

    competition_id: int
    competition_name: str
    season_id: int
    season_name: str
    downloaded_at: str
    match_ids: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> CompetitionRecord:
        return cls(
            competition_id=d["competition_id"],
            competition_name=d["competition_name"],
            season_id=d["season_id"],
            season_name=d["season_name"],
            downloaded_at=d["downloaded_at"],
            match_ids=d.get("match_ids", []),
        )


@dataclass
class DownloadManifest:
    """
    Complete record of what has been downloaded.

    Persisted as data/raw/manifest.json after every download session.
    """

    version: str = MANIFEST_VERSION
    mode: str = "unknown"           # "sample" | "competition" | "full"
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())
    competitions: list[CompetitionRecord] = field(default_factory=list)
    events_downloaded: list[int] = field(default_factory=list)
    lineups_downloaded: list[int] = field(default_factory=list)

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def total_matches(self) -> int:
        return sum(len(c.match_ids) for c in self.competitions)

    @property
    def total_events(self) -> int:
        return len(self.events_downloaded)

    @property
    def total_lineups(self) -> int:
        return len(self.lineups_downloaded)

    def competition_seasons(self) -> list[tuple[int, int]]:
        """Return list of (competition_id, season_id) tuples."""
        return [(c.competition_id, c.season_id) for c in self.competitions]

    def all_match_ids(self) -> list[int]:
        """Return all downloaded match IDs across all competitions."""
        ids: list[int] = []
        for comp in self.competitions:
            ids.extend(comp.match_ids)
        return ids

    # ── Idempotency helpers ───────────────────────────────────────────────────

    def has_matches(self, competition_id: int, season_id: int) -> bool:
        """True if this competition+season's matches have been downloaded."""
        return any(
            c.competition_id == competition_id and c.season_id == season_id
            for c in self.competitions
        )

    def has_events(self, match_id: int) -> bool:
        """True if events for this match have been downloaded."""
        return match_id in self.events_downloaded

    def has_lineups(self, match_id: int) -> bool:
        """True if lineups for this match have been downloaded."""
        return match_id in self.lineups_downloaded

    # ── Mutation ──────────────────────────────────────────────────────────────

    def record_competition(
        self,
        competition_id: int,
        competition_name: str,
        season_id: int,
        season_name: str,
        match_ids: list[int],
    ) -> None:
        """Record that a competition+season has been downloaded."""
        # Replace existing record if present
        self.competitions = [
            c for c in self.competitions
            if not (c.competition_id == competition_id and c.season_id == season_id)
        ]
        self.competitions.append(
            CompetitionRecord(
                competition_id=competition_id,
                competition_name=competition_name,
                season_id=season_id,
                season_name=season_name,
                downloaded_at=_now(),
                match_ids=sorted(match_ids),
            )
        )
        self.updated_at = _now()

    def record_events(self, match_id: int) -> None:
        if match_id not in self.events_downloaded:
            self.events_downloaded.append(match_id)
        self.updated_at = _now()

    def record_lineups(self, match_id: int) -> None:
        if match_id not in self.lineups_downloaded:
            self.lineups_downloaded.append(match_id)
        self.updated_at = _now()

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "mode": self.mode,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "competitions": [asdict(c) for c in self.competitions],
            "events_downloaded": sorted(self.events_downloaded),
            "lineups_downloaded": sorted(self.lineups_downloaded),
        }

    @classmethod
    def from_dict(cls, d: dict) -> DownloadManifest:
        return cls(
            version=d.get("version", MANIFEST_VERSION),
            mode=d.get("mode", "unknown"),
            created_at=d.get("created_at", _now()),
            updated_at=d.get("updated_at", _now()),
            competitions=[
                CompetitionRecord.from_dict(c) for c in d.get("competitions", [])
            ],
            events_downloaded=d.get("events_downloaded", []),
            lineups_downloaded=d.get("lineups_downloaded", []),
        )

    def summary(self) -> str:
        """Return a one-line human-readable summary."""
        return (
            f"mode={self.mode!r}  "
            f"competitions={len(self.competitions)}  "
            f"matches={self.total_matches}  "
            f"events={self.total_events}  "
            f"lineups={self.total_lineups}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Manifest manager — load / save
# ─────────────────────────────────────────────────────────────────────────────


class ManifestManager:
    """
    Loads and saves DownloadManifest to/from disk.

    Usage:
        manager = ManifestManager(raw_dir)
        manifest = manager.load()          # returns empty manifest if none exists
        manifest.record_events(match_id)
        manager.save(manifest)
    """

    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = raw_dir
        self.manifest_path = raw_dir / MANIFEST_FILE

    def exists(self) -> bool:
        return self.manifest_path.exists()

    def load(self) -> DownloadManifest:
        """
        Load the manifest from disk.

        Returns an empty DownloadManifest if no manifest file exists yet.
        """
        if not self.manifest_path.exists():
            return DownloadManifest()
        try:
            with open(self.manifest_path, encoding="utf-8") as f:
                data = json.load(f)
            return DownloadManifest.from_dict(data)
        except (json.JSONDecodeError, KeyError) as exc:
            # Manifest is corrupted — start fresh rather than abort
            return DownloadManifest()

    def save(self, manifest: DownloadManifest) -> None:
        """
        Save the manifest to disk atomically.

        Uses a temp file + rename to avoid leaving a corrupted manifest
        if the process is interrupted mid-write.
        """
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
        tmp.replace(self.manifest_path)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
