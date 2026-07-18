"""
backend/ingestion/load_data.py - StatsBomb Open Data acquisition

Responsibility: Download StatsBomb Open Data as raw JSON into data/raw/.

Design decisions:
  - Downloads the official StatsBomb open-data repository ZIP archive.
  - Extracts the archive and populates the data/raw/ folder identically to the prior implementation.
  - Applies post-extraction filtering if --competition or --sample are requested.
  - No third-party dependencies are required for ingestion (uses urllib, zipfile).
  - Idempotent: Skips download if data/raw/competitions.json exists, unless --force.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"

#: Official StatsBomb Open Data repository ZIP
STATSBOMB_ZIP_URL = (
    "https://github.com/statsbomb/open-data/archive/refs/heads/master.zip"
)


@dataclass
class DownloadSummary:
    mode: str
    downloaded_competitions: int = 0
    downloaded_matches: int = 0
    downloaded_events: int = 0
    downloaded_lineups: int = 0
    skipped_files: bool = False

    def report_lines(self) -> list[str]:
        if self.skipped_files:
            return [
                f"  Mode           : {self.mode}",
                "  Status         : Skipped (data already exists. Use --force to rebuild.)",
            ]
        return [
            f"  Mode           : {self.mode}",
            f"  Competitions   : {self.downloaded_competitions}",
            f"  Matches        : {self.downloaded_matches}",
            f"  Events         : {self.downloaded_events}",
            f"  Lineups        : {self.downloaded_lineups}",
        ]


class StatsBombDownloader:
    def __init__(self, raw_dir: Path = RAW_DIR, force: bool = False) -> None:
        self.raw_dir = raw_dir
        self.force = force

    def _is_populated(self) -> bool:
        return (self.raw_dir / "competitions.json").exists()

    def _download_and_extract(self) -> Path:
        """Downloads the ZIP and extracts it to a temporary directory. Returns the path to temp dir."""
        temp_dir = Path(tempfile.mkdtemp(prefix="athena_statsbomb_"))
        zip_path = temp_dir / "master.zip"

        logger.info("download.start", url=STATSBOMB_ZIP_URL)
        print(">> Downloading StatsBomb repository archive (~100MB)...")
        req = urllib.request.Request(
            STATSBOMB_ZIP_URL,
            headers={"User-Agent": "Athena/1.0 (football-intelligence; portfolio)"},
        )
        with (
            urllib.request.urlopen(req, timeout=120) as response,
            open(zip_path, "wb") as out_file,
        ):
            shutil.copyfileobj(response, out_file)

        logger.info("extract.start", zip_path=str(zip_path))
        print(">> Extracting archive...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)

        # The extracted zip has a root folder `open-data-master`
        extracted_data_dir = temp_dir / "open-data-master" / "data"
        if not extracted_data_dir.exists():
            raise RuntimeError(
                f"Expected data directory not found in extracted archive: {extracted_data_dir}"
            )

        return temp_dir

    def _clean_raw_dir(self):
        """Wipes the raw directory for a fresh extraction."""
        if self.raw_dir.exists():
            shutil.rmtree(self.raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def _copy_matches_events_lineups(
        self,
        source_data_dir: Path,
        comp_id: int,
        season_id: int,
        n_matches: int | None,
        summary: DownloadSummary,
    ):
        """Copies matches, events, and lineups for a given competition+season."""
        matches_src = source_data_dir / "matches" / str(comp_id) / f"{season_id}.json"
        if not matches_src.exists():
            return

        # Copy the matches json
        matches_dest = self.raw_dir / "matches" / str(comp_id) / f"{season_id}.json"
        matches_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(matches_src, matches_dest)
        summary.downloaded_matches += 1

        with open(matches_src, encoding="utf-8") as f:
            match_list = json.load(f)

        target_matches = match_list if n_matches is None else match_list[:n_matches]

        for match in target_matches:
            match_id = match.get("match_id")
            if not match_id:
                continue

            # Events
            events_src = source_data_dir / "events" / f"{match_id}.json"
            if events_src.exists():
                events_dest = self.raw_dir / "events" / f"{match_id}.json"
                events_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(events_src, events_dest)
                summary.downloaded_events += 1

            # Lineups
            lineups_src = source_data_dir / "lineups" / f"{match_id}.json"
            if lineups_src.exists():
                lineups_dest = self.raw_dir / "lineups" / f"{match_id}.json"
                lineups_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(lineups_src, lineups_dest)
                summary.downloaded_lineups += 1

    def run_sample(
        self, n_matches: int = 5, competition_id: int = 11
    ) -> DownloadSummary:
        summary = DownloadSummary(mode="sample")
        if self._is_populated() and not self.force:
            summary.skipped_files = True
            _print_summary(summary)
            return summary

        temp_dir = self._download_and_extract()
        source_data = temp_dir / "open-data-master" / "data"

        try:
            self._clean_raw_dir()

            # Competitions
            comps_src = source_data / "competitions.json"
            with open(comps_src, encoding="utf-8") as f:
                comps = json.load(f)

            # Find the requested competition and its first season
            seasons = [c for c in comps if c.get("competition_id") == competition_id]
            if not seasons:
                raise ValueError(f"Competition ID {competition_id} not found.")
            target_season = seasons[0]

            shutil.copy2(comps_src, self.raw_dir / "competitions.json")
            summary.downloaded_competitions = 1

            self._copy_matches_events_lineups(
                source_data,
                target_season["competition_id"],
                target_season["season_id"],
                n_matches,
                summary,
            )

        finally:
            shutil.rmtree(temp_dir)

        _print_summary(summary)
        return summary

    def run_competition(
        self, competition_name: str | None = None, competition_id: int | None = None
    ) -> DownloadSummary:
        if competition_name is None and competition_id is None:
            raise ValueError("Provide competition_name or competition_id.")

        summary = DownloadSummary(mode="competition")
        if self._is_populated() and not self.force:
            summary.skipped_files = True
            _print_summary(summary)
            return summary

        temp_dir = self._download_and_extract()
        source_data = temp_dir / "open-data-master" / "data"

        try:
            self._clean_raw_dir()

            comps_src = source_data / "competitions.json"
            shutil.copy2(comps_src, self.raw_dir / "competitions.json")
            summary.downloaded_competitions = 1

            with open(comps_src, encoding="utf-8") as f:
                comps = json.load(f)

            seasons = [
                c
                for c in comps
                if (
                    competition_name is None
                    or c.get("competition_name") == competition_name
                )
                and (
                    competition_id is None or c.get("competition_id") == competition_id
                )
            ]

            if not seasons:
                raise ValueError("Competition not found.")

            for target_season in seasons:
                self._copy_matches_events_lineups(
                    source_data,
                    target_season["competition_id"],
                    target_season["season_id"],
                    None,
                    summary,
                )

        finally:
            shutil.rmtree(temp_dir)

        _print_summary(summary)
        return summary

    def run_full(self) -> DownloadSummary:
        summary = DownloadSummary(mode="full")
        if self._is_populated() and not self.force:
            summary.skipped_files = True
            _print_summary(summary)
            return summary

        temp_dir = self._download_and_extract()
        source_data = temp_dir / "open-data-master" / "data"

        try:
            self._clean_raw_dir()

            # For a full run, we can just copy the relevant directories directly
            shutil.copy2(
                source_data / "competitions.json", self.raw_dir / "competitions.json"
            )
            summary.downloaded_competitions = 1

            for d in ["matches", "events", "lineups"]:
                src_d = source_data / d
                dest_d = self.raw_dir / d
                if src_d.exists():
                    shutil.copytree(src_d, dest_d)

            summary.downloaded_matches = len(
                list((self.raw_dir / "matches").rglob("*.json"))
            )
            summary.downloaded_events = len(
                list((self.raw_dir / "events").rglob("*.json"))
            )
            summary.downloaded_lineups = len(
                list((self.raw_dir / "lineups").rglob("*.json"))
            )

        finally:
            shutil.rmtree(temp_dir)

        _print_summary(summary)
        return summary

    def list_competitions(self) -> None:
        if not self._is_populated():
            url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/competitions.json"
            req = urllib.request.Request(url, headers={"User-Agent": "Athena/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                competitions = json.loads(resp.read().decode("utf-8"))
        else:
            with open(self.raw_dir / "competitions.json", encoding="utf-8") as f:
                competitions = json.load(f)

        print()
        print("  StatsBomb Open Data - Available Competitions")
        print("  -" * 30)
        print(f"  {'ID':>5}  {'Season ID':>9}  {'Competition':<30}  {'Season'}")
        print(f"  {'-' * 5}  {'-' * 9}  {'-' * 30}  {'-' * 15}")
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


def _print_summary(summary: DownloadSummary) -> None:
    print()
    print("  ==============================================")
    print("    Athena - Download Complete")
    print("  ==============================================")
    for line in summary.report_lines():
        print(line)
    print("  ==============================================")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Athena - StatsBomb Open Data acquisition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--sample", action="store_true", help="Download a small sample")
    parser.add_argument("--n-matches", type=int, default=5, metavar="N")
    parser.add_argument("--competition", type=str, default=None, metavar="NAME")
    parser.add_argument("--competition-id", type=int, default=None, metavar="ID")
    parser.add_argument("--list-competitions", action="store_true")
    parser.add_argument("--force", action="store_true")

    # We ignore --delay now, but keep it in argparse for backwards compatibility
    parser.add_argument("--delay", type=float, default=0.4, help=argparse.SUPPRESS)

    args = parser.parse_args()

    downloader = StatsBombDownloader(raw_dir=RAW_DIR, force=args.force)

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

    downloader.run_full()


if __name__ == "__main__":
    main()
