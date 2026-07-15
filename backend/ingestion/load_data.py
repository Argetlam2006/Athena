"""
backend/ingestion/load_data.py — StatsBomb Open Data acquisition

Responsibility: Download StatsBomb Open Data as raw JSON into data/raw/.

Design decisions:
  - Downloads directly from StatsBomb's GitHub raw URL via urllib (stdlib, no
    extra dependency). This preserves the original JSON format exactly.
  - Saves files mirroring the StatsBomb open-data repository structure:
      data/raw/competitions.json
      data/raw/matches/{competition_id}/{season_id}.json
      data/raw/events/{match_id}.json
      data/raw/lineups/{match_id}.json
  - Every download is idempotent: existing files are skipped unless --force
    is given. The manifest records what has been downloaded.
  - statsbombpy is NOT imported here. It is used in the ETL layer (Sprint 1.3)
    to read from local files with its built-in parsers.

StatsBomb Open Data: CC BY-SA 4.0 — https://github.com/statsbomb/open-data
Attribution required: StatsBomb — https://statsbomb.com

Usage:
    python -m backend.ingestion.load_data --sample
    python -m backend.ingestion.load_data --competition "La Liga"
    python -m backend.ingestion.load_data --list-competitions
    python -m backend.ingestion.load_data             # full catalogue
    make data
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from backend.ingestion.manifest import DownloadManifest, ManifestManager
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"

#: StatsBomb Open Data raw GitHub URL. Every file is fetched from here.
STATSBOMB_BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

#: Polite inter-request delay in seconds (default). Prevents hammering GitHub CDN.
DEFAULT_DELAY_S: float = 0.4

#: Maximum retry attempts per file.
MAX_RETRIES: int = 3


# ─────────────────────────────────────────────────────────────────────────────
# Download summary
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DownloadSummary:
    """
    Result returned by every run_* method.

    downloaded_* counts how many new files were saved.
    skipped_*   counts how many were already present (idempotent).
    failed_*    counts how many could not be retrieved.
    """

    mode: str
    downloaded_competitions: int = 0
    downloaded_matches: int = 0
    downloaded_events: int = 0
    downloaded_lineups: int = 0
    skipped_competitions: int = 0
    skipped_matches: int = 0
    skipped_events: int = 0
    skipped_lineups: int = 0
    failed_matches: int = 0
    failed_events: int = 0
    failed_lineups: int = 0

    @property
    def total_downloaded(self) -> int:
        return (
            self.downloaded_competitions
            + self.downloaded_matches
            + self.downloaded_events
            + self.downloaded_lineups
        )

    @property
    def total_skipped(self) -> int:
        return (
            self.skipped_competitions
            + self.skipped_matches
            + self.skipped_events
            + self.skipped_lineups
        )

    @property
    def total_failed(self) -> int:
        return self.failed_matches + self.failed_events + self.failed_lineups

    def report_lines(self) -> list[str]:
        return [
            f"  Mode           : {self.mode}",
            f"  Downloaded     : {self.total_downloaded} files",
            f"  Skipped        : {self.total_skipped} files (already present)",
            f"  Failed         : {self.total_failed} files",
            f"  ├ competitions : {self.downloaded_competitions} downloaded, {self.skipped_competitions} skipped",
            f"  ├ matches      : {self.downloaded_matches} downloaded, {self.skipped_matches} skipped, {self.failed_matches} failed",
            f"  ├ events       : {self.downloaded_events} downloaded, {self.skipped_events} skipped, {self.failed_events} failed",
            f"  └ lineups      : {self.downloaded_lineups} downloaded, {self.skipped_lineups} skipped, {self.failed_lineups} failed",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Core downloader
# ─────────────────────────────────────────────────────────────────────────────


class StatsBombDownloader:
    """
    Downloads StatsBomb Open Data JSON files from GitHub.

    Every public method is idempotent — running twice produces the same result.
    Existing files are never overwritten unless `force=True`.
    """

    def __init__(
        self,
        raw_dir: Path = RAW_DIR,
        delay_s: float = DEFAULT_DELAY_S,
        force: bool = False,
    ) -> None:
        self.raw_dir = raw_dir
        self.delay_s = delay_s
        self.force = force
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_manager = ManifestManager(raw_dir)

    # ── Low-level HTTP ────────────────────────────────────────────────────────

    def _fetch_json(self, url: str) -> list | dict:
        """
        Fetch JSON from a URL with exponential-backoff retry.

        Raises:
            urllib.error.HTTPError: on 404 (file not in StatsBomb) — not retried
            urllib.error.URLError:  on persistent network failure
        """
        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Athena/1.0 (football-intelligence; portfolio)"
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise  # not retried — file simply does not exist
                last_exc = exc
            except urllib.error.URLError as exc:
                last_exc = exc

            wait = self.delay_s * (2**attempt)
            logger.warning(
                "download.retry",
                url=url,
                attempt=attempt + 1,
                max=MAX_RETRIES,
                wait_s=wait,
            )
            time.sleep(wait)

        raise last_exc  # type: ignore[misc]

    def _save_json(self, data: list | dict, dest: Path) -> None:
        """Save data as compact UTF-8 JSON (no indent = smaller files)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    # ── File-level downloads ──────────────────────────────────────────────────

    def download_competitions(self) -> tuple[list[dict], bool]:
        """
        Download competitions.json.

        Returns:
            (competitions_list, was_downloaded)
            was_downloaded = False if file already existed and force=False
        """
        dest = self.raw_dir / "competitions.json"
        if dest.exists() and not self.force:
            logger.info("download.skip", file="competitions.json", reason="exists")
            with open(dest, encoding="utf-8") as f:
                return json.load(f), False

        url = f"{STATSBOMB_BASE_URL}/competitions.json"
        logger.info("download.start", file="competitions.json")
        data = self._fetch_json(url)
        self._save_json(data, dest)
        logger.info("download.ok", file="competitions.json", records=len(data))
        time.sleep(self.delay_s)
        return data, True

    def download_matches(
        self, competition_id: int, season_id: int, manifest: DownloadManifest
    ) -> tuple[list[dict], bool]:
        """
        Download matches/{competition_id}/{season_id}.json.

        Returns:
            (matches_list, was_downloaded)
        """
        dest = self.raw_dir / "matches" / str(competition_id) / f"{season_id}.json"
        if (
            dest.exists()
            and not self.force
            and manifest.has_matches(competition_id, season_id)
        ):
            logger.info(
                "download.skip",
                file=f"matches/{competition_id}/{season_id}.json",
                reason="exists",
            )
            with open(dest, encoding="utf-8") as f:
                return json.load(f), False

        url = f"{STATSBOMB_BASE_URL}/matches/{competition_id}/{season_id}.json"
        label = f"matches/{competition_id}/{season_id}.json"
        logger.info("download.start", file=label)
        data = self._fetch_json(url)
        self._save_json(data, dest)
        logger.info("download.ok", file=label, records=len(data))
        time.sleep(self.delay_s)
        return data, True

    def download_events(self, match_id: int, manifest: DownloadManifest) -> bool:
        """
        Download events/{match_id}.json.

        Returns True if the file was fetched, False if skipped.
        """
        dest = self.raw_dir / "events" / f"{match_id}.json"
        if dest.exists() and not self.force and manifest.has_events(match_id):
            return False

        url = f"{STATSBOMB_BASE_URL}/events/{match_id}.json"
        logger.info("download.start", file=f"events/{match_id}.json")
        data = self._fetch_json(url)
        self._save_json(data, dest)
        logger.info(
            "download.ok",
            file=f"events/{match_id}.json",
            events=len(data) if isinstance(data, list) else "?",
        )
        time.sleep(self.delay_s)
        return True

    def download_lineups(self, match_id: int, manifest: DownloadManifest) -> bool:
        """
        Download lineups/{match_id}.json.

        Returns True if the file was fetched, False if skipped.
        """
        dest = self.raw_dir / "lineups" / f"{match_id}.json"
        if dest.exists() and not self.force and manifest.has_lineups(match_id):
            return False

        url = f"{STATSBOMB_BASE_URL}/lineups/{match_id}.json"
        logger.info("download.start", file=f"lineups/{match_id}.json")
        data = self._fetch_json(url)
        self._save_json(data, dest)
        logger.info("download.ok", file=f"lineups/{match_id}.json")
        time.sleep(self.delay_s)
        return True

    # ── Match-level pipeline ──────────────────────────────────────────────────

    def _process_matches(
        self,
        match_list: list[dict],
        manifest: DownloadManifest,
        summary: DownloadSummary,
        n_limit: int | None = None,
    ) -> list[int]:
        """
        Download events and lineups for each match in match_list.

        Args:
            match_list: List of match dicts from matches/{comp}/{season}.json
            manifest:   Current manifest (mutated in-place)
            summary:    Current summary (mutated in-place)
            n_limit:    If set, stop after this many matches (sample mode)

        Returns list of successfully processed match IDs.
        """
        processed: list[int] = []
        target = match_list if n_limit is None else match_list[:n_limit]

        for match in target:
            match_id = match.get("match_id")
            if match_id is None:
                logger.warning("download.match.no_id", match=str(match)[:120])
                continue

            # Events
            try:
                if self.download_events(match_id, manifest):
                    summary.downloaded_events += 1
                    manifest.record_events(match_id)
                else:
                    summary.skipped_events += 1
            except urllib.error.HTTPError as exc:
                logger.warning(
                    "download.events.fail",
                    match_id=match_id,
                    status=exc.code,
                )
                summary.failed_events += 1
            except Exception as exc:
                logger.warning(
                    "download.events.fail",
                    match_id=match_id,
                    reason=str(exc)[:120],
                )
                summary.failed_events += 1

            # Lineups
            try:
                if self.download_lineups(match_id, manifest):
                    summary.downloaded_lineups += 1
                    manifest.record_lineups(match_id)
                else:
                    summary.skipped_lineups += 1
            except urllib.error.HTTPError as exc:
                logger.warning(
                    "download.lineups.fail",
                    match_id=match_id,
                    status=exc.code,
                )
                summary.failed_lineups += 1
            except Exception as exc:
                logger.warning(
                    "download.lineups.fail",
                    match_id=match_id,
                    reason=str(exc)[:120],
                )
                summary.failed_lineups += 1

            processed.append(match_id)

        return processed

    # ── Run modes ─────────────────────────────────────────────────────────────

    def run_sample(
        self,
        n_matches: int = 5,
        competition_id: int = 11,
    ) -> DownloadSummary:
        """
        Download a small representative sample for local demonstration.

        Default: La Liga (competition_id=11), first available season, 5 matches.
        This is enough to run the analytics pipeline end-to-end.

        Args:
            n_matches:       Number of matches to download (default 5)
            competition_id:  Competition to sample from (default 11 = La Liga)
        """
        summary = DownloadSummary(mode="sample")
        manifest = self._manifest_manager.load()
        manifest.mode = "sample"

        logger.info(
            "pipeline.start",
            mode="sample",
            competition_id=competition_id,
            n_matches=n_matches,
        )

        # Step 1 — competitions
        try:
            competitions, was_new = self.download_competitions()
            summary.downloaded_competitions += int(was_new)
            summary.skipped_competitions += int(not was_new)
        except Exception as exc:
            logger.error("pipeline.competitions.fail", reason=str(exc))
            return summary

        # Step 2 — find a season for this competition
        seasons = [c for c in competitions if c.get("competition_id") == competition_id]
        if not seasons:
            logger.error(
                "pipeline.no_seasons",
                competition_id=competition_id,
                message=(
                    f"competition_id={competition_id} not found. "
                    f"Run --list-competitions to see available IDs."
                ),
            )
            return summary

        # Use the first season (most recently added in StatsBomb)
        target = seasons[0]
        season_id = target["season_id"]
        comp_name = target.get("competition_name", str(competition_id))
        season_name = target.get("season_name", str(season_id))

        logger.info(
            "pipeline.sample.target",
            competition=comp_name,
            season=season_name,
        )

        # Step 3 — matches
        try:
            match_list, was_new = self.download_matches(
                competition_id, season_id, manifest
            )
            summary.downloaded_matches += int(was_new)
            summary.skipped_matches += int(not was_new)
        except Exception as exc:
            logger.error("pipeline.matches.fail", reason=str(exc))
            return summary

        # Step 4 — events and lineups for first n_matches
        match_ids = self._process_matches(
            match_list, manifest, summary, n_limit=n_matches
        )

        # Step 5 — update manifest
        manifest.record_competition(
            competition_id=competition_id,
            competition_name=comp_name,
            season_id=season_id,
            season_name=season_name,
            match_ids=match_ids,
        )
        self._manifest_manager.save(manifest)

        logger.info("pipeline.complete", mode="sample", **_summary_dict(summary))
        _print_summary(summary)
        return summary

    def run_competition(
        self,
        competition_name: str | None = None,
        competition_id: int | None = None,
    ) -> DownloadSummary:
        """
        Download all matches, events and lineups for one competition.

        One of competition_name or competition_id must be provided.

        Args:
            competition_name: e.g. "La Liga" (case-sensitive)
            competition_id:   e.g. 11
        """
        if competition_name is None and competition_id is None:
            raise ValueError("Provide competition_name or competition_id.")

        summary = DownloadSummary(mode="competition")
        manifest = self._manifest_manager.load()
        manifest.mode = "competition"

        logger.info(
            "pipeline.start",
            mode="competition",
            competition_name=competition_name,
            competition_id=competition_id,
        )

        # Competitions
        try:
            competitions, was_new = self.download_competitions()
            summary.downloaded_competitions += int(was_new)
            summary.skipped_competitions += int(not was_new)
        except Exception as exc:
            logger.error("pipeline.competitions.fail", reason=str(exc))
            return summary

        # Filter seasons for this competition
        seasons = [
            c
            for c in competitions
            if (
                competition_name is None
                or c.get("competition_name") == competition_name
            )
            and (competition_id is None or c.get("competition_id") == competition_id)
        ]

        if not seasons:
            logger.error(
                "pipeline.no_match",
                competition_name=competition_name,
                competition_id=competition_id,
                message="Competition not found. Run --list-competitions to see options.",
            )
            return summary

        for entry in seasons:
            comp_id = entry["competition_id"]
            s_id = entry["season_id"]
            comp_name = entry.get("competition_name", str(comp_id))
            s_name = entry.get("season_name", str(s_id))

            logger.info(
                "pipeline.season.start",
                competition=comp_name,
                season=s_name,
            )

            try:
                match_list, was_new = self.download_matches(comp_id, s_id, manifest)
                summary.downloaded_matches += int(was_new)
                summary.skipped_matches += int(not was_new)
            except Exception as exc:
                logger.warning(
                    "pipeline.matches.fail",
                    competition=comp_name,
                    season=s_name,
                    reason=str(exc),
                )
                summary.failed_matches += 1
                continue

            match_ids = self._process_matches(match_list, manifest, summary)
            manifest.record_competition(
                competition_id=comp_id,
                competition_name=comp_name,
                season_id=s_id,
                season_name=s_name,
                match_ids=match_ids,
            )
            self._manifest_manager.save(manifest)

        logger.info("pipeline.complete", mode="competition", **_summary_dict(summary))
        _print_summary(summary)
        return summary

    def run_full(self) -> DownloadSummary:
        """
        Download the complete StatsBomb Open Data catalogue.

        This fetches every competition, season, match, event and lineup
        available. Expect several gigabytes of data and 20–40 minutes runtime.

        Runs are resumable: existing files are skipped automatically.
        """
        summary = DownloadSummary(mode="full")
        manifest = self._manifest_manager.load()
        manifest.mode = "full"

        logger.info("pipeline.start", mode="full")

        try:
            competitions, was_new = self.download_competitions()
            summary.downloaded_competitions += int(was_new)
            summary.skipped_competitions += int(not was_new)
        except Exception as exc:
            logger.error("pipeline.competitions.fail", reason=str(exc))
            return summary

        logger.info("pipeline.full.scope", total_seasons=len(competitions))

        for entry in competitions:
            comp_id = entry["competition_id"]
            s_id = entry["season_id"]
            comp_name = entry.get("competition_name", str(comp_id))
            s_name = entry.get("season_name", str(s_id))

            try:
                match_list, was_new = self.download_matches(comp_id, s_id, manifest)
                summary.downloaded_matches += int(was_new)
                summary.skipped_matches += int(not was_new)
            except urllib.error.HTTPError as exc:
                logger.warning(
                    "pipeline.matches.fail",
                    competition=comp_name,
                    season=s_name,
                    status=exc.code,
                )
                summary.failed_matches += 1
                continue
            except Exception as exc:
                logger.warning(
                    "pipeline.matches.fail",
                    competition=comp_name,
                    season=s_name,
                    reason=str(exc),
                )
                summary.failed_matches += 1
                continue

            match_ids = self._process_matches(match_list, manifest, summary)
            manifest.record_competition(
                competition_id=comp_id,
                competition_name=comp_name,
                season_id=s_id,
                season_name=s_name,
                match_ids=match_ids,
            )
            # Save manifest after each competition to enable crash recovery
            self._manifest_manager.save(manifest)

        logger.info("pipeline.complete", mode="full", **_summary_dict(summary))
        _print_summary(summary)
        return summary

    def list_competitions(self) -> None:
        """Print the available competitions catalogue and exit."""
        try:
            competitions, _ = self.download_competitions()
        except Exception as exc:
            print(f"Error fetching competitions: {exc}")
            return

        print()
        print("  StatsBomb Open Data — Available Competitions")
        print("  ─" * 30)
        print(f"  {'ID':>5}  {'Season ID':>9}  {'Competition':<30}  {'Season'}")
        print(f"  {'─' * 5}  {'─' * 9}  {'─' * 30}  {'─' * 15}")
        for c in sorted(
            competitions,
            key=lambda x: (x.get("competition_name", ""), x.get("season_name", "")),
        ):
            print(
                f"  {c.get('competition_id', '?'):>5}  "
                f"{c.get('season_id', '?'):>9}  "
                f"{c.get('competition_name', '?'):<30}  "
                f"{c.get('season_name', '?')}"
            )
        print()
        print(f"  Total: {len(competitions)} competition-season combinations")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helpers
# ─────────────────────────────────────────────────────────────────────────────


def _summary_dict(s: DownloadSummary) -> dict:
    return {
        "downloaded": s.total_downloaded,
        "skipped": s.total_skipped,
        "failed": s.total_failed,
    }


def _print_summary(summary: DownloadSummary) -> None:
    print()
    print("  ══════════════════════════════════════════════")
    print("    Athena — Download Complete")
    print("  ══════════════════════════════════════════════")
    for line in summary.report_lines():
        print(line)
    print("  ══════════════════════════════════════════════")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Athena — StatsBomb Open Data acquisition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.ingestion.load_data --sample
  python -m backend.ingestion.load_data --sample --n-matches 10
  python -m backend.ingestion.load_data --competition "La Liga"
  python -m backend.ingestion.load_data --competition-id 16
  python -m backend.ingestion.load_data --list-competitions
  python -m backend.ingestion.load_data            (full catalogue)
  make data
        """,
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Download a small sample (default: 5 matches from La Liga)",
    )
    parser.add_argument(
        "--n-matches",
        type=int,
        default=5,
        metavar="N",
        help="Number of matches to download in sample mode (default: 5)",
    )
    parser.add_argument(
        "--competition",
        type=str,
        default=None,
        metavar="NAME",
        help="Download a specific competition by name, e.g. 'La Liga'",
    )
    parser.add_argument(
        "--competition-id",
        type=int,
        default=None,
        metavar="ID",
        help="Download a specific competition by ID, e.g. 11",
    )
    parser.add_argument(
        "--list-competitions",
        action="store_true",
        help="Print available competitions and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download files even if they already exist",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_S,
        metavar="SECONDS",
        help=f"Delay between requests in seconds (default: {DEFAULT_DELAY_S})",
    )
    args = parser.parse_args()

    downloader = StatsBombDownloader(
        raw_dir=RAW_DIR,
        delay_s=args.delay,
        force=args.force,
    )

    if args.list_competitions:
        downloader.list_competitions()
        return

    if args.sample:
        downloader.run_sample(n_matches=args.n_matches)
        return

    if args.competition or args.competition_id:
        downloader.run_competition(
            competition_name=args.competition,
            competition_id=args.competition_id,
        )
        return

    # Default: full catalogue
    downloader.run_full()


if __name__ == "__main__":
    main()
