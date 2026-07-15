"""
backend/intelligence/store.py — The Intelligence Store.

This module serializes the deterministic output of the Football Intelligence
Engine into highly optimized Parquet files.
It also creates lightweight metadata indexes for instantaneous frontend loading.
"""

import json
import logging
from pathlib import Path
from typing import Sequence
import pandas as pd
import duckdb
from dataclasses import asdict
from pydantic import TypeAdapter

from backend.warehouse.connection import DB_PATH
from shared.schemas import PlayerProfile, TeamProfile

logger = logging.getLogger(__name__)

STORE_DIR = Path("data/warehouse")
FINGERPRINT_PATH = STORE_DIR / "intelligence_fingerprint.json"
PLAYER_PROFILES_PATH = STORE_DIR / "player_profiles.parquet"
TEAM_PROFILES_PATH = STORE_DIR / "team_profiles.parquet"
PLAYER_INDEX_PATH = STORE_DIR / "player_index.parquet"
TEAM_INDEX_PATH = STORE_DIR / "team_index.parquet"

# Reusable adapters for mapping dictionaries back to dataclasses
_player_adapter = TypeAdapter(PlayerProfile)
_team_adapter = TypeAdapter(TeamProfile)

class IntelligenceStore:
    def __init__(self):
        STORE_DIR.mkdir(parents=True, exist_ok=True)

    def _generate_fingerprint(self) -> dict:
        """Generate a deterministic fingerprint of the current warehouse state."""
        if not DB_PATH.exists():
            return {}
            
        con = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            # Query row counts of the core base tables for fingerprinting
            tables = ["competitions", "matches", "events", "lineups"]
            counts = {}
            for t in tables:
                try:
                    counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                except duckdb.CatalogException:
                    counts[t] = 0
            return counts
        finally:
            con.close()

    def is_valid(self) -> bool:
        """Check if the Intelligence Store is up-to-date with the warehouse."""
        paths = [
            PLAYER_PROFILES_PATH, TEAM_PROFILES_PATH, 
            PLAYER_INDEX_PATH, TEAM_INDEX_PATH, FINGERPRINT_PATH
        ]
        if not all(p.exists() for p in paths):
            return False

        try:
            with open(FINGERPRINT_PATH, "r") as f:
                stored = json.load(f)
            current = self._generate_fingerprint()
            return stored == current
        except Exception:
            return False

    def save(self, players: Sequence[PlayerProfile], teams: Sequence[TeamProfile]) -> None:
        """Serialize profiles and generate lightweight discovery indexes."""
        logger.info("Building Intelligence Store...")
        
        # 1. Full Profiles (Parquet for players, JSON for teams to avoid struct schema issues)
        if players:
            df_players = pd.DataFrame([asdict(p) for p in players])
            df_players.to_parquet(PLAYER_PROFILES_PATH, engine="pyarrow", index=False)
            
            # Player Metadata Index
            index_data = [{
                "player_id": p.player_id,
                "player_name": p.player_name,
                "normalized_name": p.player_name.lower(),
                "team_name": p.team_name,
                "position": p.position_group,
                "minutes_played": p.minutes_played,
                "age": p.age_years,
                "competition": p.competition,
                "season": p.season
            } for p in players]
            pd.DataFrame(index_data).to_parquet(PLAYER_INDEX_PATH, engine="pyarrow", index=False)
        else:
            pd.DataFrame().to_parquet(PLAYER_PROFILES_PATH, engine="pyarrow", index=False)
            pd.DataFrame().to_parquet(PLAYER_INDEX_PATH, engine="pyarrow", index=False)

        if teams:
            with open(TEAM_PROFILES_PATH.with_suffix(".json"), "w") as f:
                json.dump([asdict(t) for t in teams], f)
            
            # Team Metadata Index
            team_index_data = [{
                "team_id": t.team_id,
                "team_name": t.team_name,
                "competition": t.competition,
                "season": t.season
            } for t in teams]
            pd.DataFrame(team_index_data).to_parquet(TEAM_INDEX_PATH, engine="pyarrow", index=False)
        else:
            with open(TEAM_PROFILES_PATH.with_suffix(".json"), "w") as f:
                json.dump([], f)
            pd.DataFrame().to_parquet(TEAM_INDEX_PATH, engine="pyarrow", index=False)

        # 2. Fingerprint Validation
        with open(FINGERPRINT_PATH, "w") as f:
            json.dump(self._generate_fingerprint(), f)
            
        logger.info("Intelligence Store serialized successfully.")

    def get_player_index(self) -> pd.DataFrame:
        """Load lightweight player index for O(1) rendering/searching."""
        if not PLAYER_INDEX_PATH.exists():
            return pd.DataFrame()
        return pd.read_parquet(PLAYER_INDEX_PATH)

    def get_team_index(self) -> pd.DataFrame:
        if not TEAM_INDEX_PATH.exists():
            return pd.DataFrame()
        return pd.read_parquet(TEAM_INDEX_PATH)

    def get_player(self, player_id: int) -> PlayerProfile | None:
        """O(1) lazy loading via DuckDB predicate pushdown."""
        if not PLAYER_PROFILES_PATH.exists():
            return None
            
        con = duckdb.connect(":memory:")
        try:
            query = f"SELECT * FROM read_parquet('{PLAYER_PROFILES_PATH}') WHERE player_id = ?"
            df = con.execute(query, [player_id]).fetchdf()
            if df.empty:
                return None
            dict_row = df.to_dict(orient="records")[0]
            
            # Handle nested duckdb dicts for schemas 
            return _player_adapter.validate_python(dict_row)
        except Exception as e:
            logger.error(f"Failed to load player {player_id}: {e}")
            return None
        finally:
            con.close()

    def get_team(self, team_id: int) -> TeamProfile | None:
        """O(1) lazy loading for team profiles (JSON)."""
        json_path = TEAM_PROFILES_PATH.with_suffix(".json")
        if not json_path.exists():
            return None
            
        try:
            with open(json_path, "r") as f:
                teams = json.load(f)
            for t in teams:
                if t["team_id"] == team_id:
                    return _team_adapter.validate_python(t)
            return None
        except Exception as e:
            logger.error(f"Failed to load team {team_id}: {e}")
            return None
