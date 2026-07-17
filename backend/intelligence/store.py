"""
backend/intelligence/store.py - The Intelligence Store.

This module serializes the deterministic output of the Football Intelligence
Engine into highly optimized Parquet files.
It also creates lightweight metadata indexes for instantaneous frontend loading.
"""

import json
import logging
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import duckdb
import pandas as pd
from pydantic import TypeAdapter

from backend.warehouse.connection import DB_PATH
from shared.schemas import CollectiveProfile, PlayerProfile, ProfileType

logger = logging.getLogger(__name__)

STORE_DIR = Path("data/warehouse")
FINGERPRINT_PATH = STORE_DIR / "intelligence_fingerprint.json"
PLAYER_PROFILES_PATH = STORE_DIR / "player_profiles.parquet"
COLLECTIVE_PROFILES_PATH = STORE_DIR / "collective_profiles.json"
PLAYER_INDEX_PATH = STORE_DIR / "player_index.parquet"

# Reusable adapters for mapping dictionaries back to dataclasses
_player_adapter = TypeAdapter(PlayerProfile)
_collective_adapter = TypeAdapter(CollectiveProfile)


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

            from shared.constants import (
                ARCHETYPE_VERSION,
                MODEL_VERSION,
                SCHEMA_VERSION,
                WEIGHTING_VERSION,
            )

            return {
                "row_counts": counts,
                "model_version": MODEL_VERSION,
                "schema_version": SCHEMA_VERSION,
                "weighting_version": WEIGHTING_VERSION,
                "archetype_version": ARCHETYPE_VERSION,
            }
        finally:
            con.close()

    def is_valid(self) -> bool:
        """Check if the Intelligence Store is up-to-date with the warehouse."""
        paths = [PLAYER_PROFILES_PATH, PLAYER_INDEX_PATH, FINGERPRINT_PATH]
        if not all(p.exists() for p in paths):
            return False

        try:
            with open(FINGERPRINT_PATH) as f:
                stored = json.load(f)
            current = self._generate_fingerprint()
            return stored == current
        except Exception:
            return False

    def save(
        self,
        players: Sequence[PlayerProfile],
        collectives: Sequence[CollectiveProfile] = None,
    ) -> None:
        """Serialize profiles and generate lightweight discovery indexes."""
        logger.info("Building Intelligence Store...")

        # 1. Full Profiles (Parquet for players)
        if players:
            dicts = []
            complex_keys = [
                "capability_profile",
                "feature_vector",
                "player_attributes",
                "rating_presentation",
                "archetype_profile",
            ]
            for p in players:
                d = asdict(p)
                for key in complex_keys:
                    if d.get(key) is not None:
                        d[key] = json.dumps(d[key])
                dicts.append(d)
            df_players = pd.DataFrame(dicts)
            df_players.to_parquet(PLAYER_PROFILES_PATH, engine="pyarrow", index=False)

            # Player Metadata Index
            index_data = [
                {
                    "player_id": p.player_id,
                    "player_name": p.player_name,
                    "normalized_name": p.player_name.lower(),
                    "team_name": p.team_name,
                    "position": p.position_group,
                    "minutes_played": p.minutes_played,
                    "age": p.age_years,
                    "competition": p.competition,
                    "season": p.season,
                    "profile_type": p.profile_type,
                }
                for p in players
            ]
            pd.DataFrame(index_data).to_parquet(
                PLAYER_INDEX_PATH, engine="pyarrow", index=False
            )
        else:
            pd.DataFrame().to_parquet(
                PLAYER_PROFILES_PATH, engine="pyarrow", index=False
            )
            pd.DataFrame().to_parquet(PLAYER_INDEX_PATH, engine="pyarrow", index=False)

        if collectives:
            with open(COLLECTIVE_PROFILES_PATH, "w") as f:
                json.dump([asdict(c) for c in collectives], f)
        else:
            with open(COLLECTIVE_PROFILES_PATH, "w") as f:
                json.dump([], f)

        # 2. Fingerprint Validation
        with open(FINGERPRINT_PATH, "w") as f:
            json.dump(self._generate_fingerprint(), f)

        logger.info("Intelligence Store serialized successfully.")

    def get_player_index(self) -> pd.DataFrame:
        """Load lightweight player index for O(1) rendering/searching."""
        if not PLAYER_INDEX_PATH.exists():
            return pd.DataFrame()
        return pd.read_parquet(PLAYER_INDEX_PATH)

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

            complex_keys = [
                "capability_profile",
                "feature_vector",
                "player_attributes",
                "rating_presentation",
                "archetype_profile",
            ]
            for key in complex_keys:
                if dict_row.get(key) and isinstance(dict_row[key], str):
                    dict_row[key] = json.loads(dict_row[key])
            return _player_adapter.validate_python(dict_row)
        except Exception as e:
            logger.error(f"Failed to load player {player_id}: {e}")
            return None
        finally:
            con.close()

    def get_player_career(self, player_id: int) -> list[PlayerProfile]:
        """O(1) lazy loading for all available career segments of a player."""
        if not PLAYER_PROFILES_PATH.exists():
            return []

        con = duckdb.connect(":memory:")
        try:
            query = f"SELECT * FROM read_parquet('{PLAYER_PROFILES_PATH}') WHERE player_id = ?"
            df = con.execute(query, [player_id]).fetchdf()
            if df.empty:
                return []

            dicts = df.to_dict(orient="records")
            complex_keys = [
                "capability_profile",
                "feature_vector",
                "player_attributes",
                "rating_presentation",
                "archetype_profile",
            ]
            for d in dicts:
                for key in complex_keys:
                    if d.get(key) and isinstance(d[key], str):
                        d[key] = json.loads(d[key])
            return [_player_adapter.validate_python(d) for d in dicts]
        except Exception as e:
            logger.error(f"Failed to load player career {player_id}: {e}")
            return []
        finally:
            con.close()

    def get_players_by_position(
        self, position: str, profile_type: ProfileType = ProfileType.CAREER
    ) -> list[PlayerProfile]:
        """Load profiles dynamically based on position to avoid full memory loads."""
        if not PLAYER_PROFILES_PATH.exists():
            return []

        con = duckdb.connect(":memory:")
        try:
            query = f"SELECT * FROM read_parquet('{PLAYER_PROFILES_PATH}') WHERE position_group = ? AND profile_type = ?"
            df = con.execute(query, [position, profile_type.value]).fetchdf()
            if df.empty:
                return []
            dicts = df.to_dict(orient="records")
            complex_keys = [
                "capability_profile",
                "feature_vector",
                "player_attributes",
                "rating_presentation",
                "archetype_profile",
            ]
            for d in dicts:
                for key in complex_keys:
                    if d.get(key) and isinstance(d[key], str):
                        d[key] = json.loads(d[key])
            return [_player_adapter.validate_python(d) for d in dicts]
        except Exception as e:
            logger.error(f"Failed to retrieve players for position {position}: {e}")
            return []
        finally:
            con.close()

    def get_all_players(
        self, profile_type: ProfileType = ProfileType.CAREER
    ) -> list[PlayerProfile]:
        """[DEVELOPER ONLY / DEBUGGING] Load all PlayerProfiles."""
        if not PLAYER_PROFILES_PATH.exists():
            return []

        con = duckdb.connect(":memory:")
        try:
            query = f"SELECT * FROM read_parquet('{PLAYER_PROFILES_PATH}') WHERE profile_type = ?"
            df = con.execute(query, [profile_type.value]).fetchdf()
            if df.empty:
                return []
            dicts = df.to_dict(orient="records")
            complex_keys = [
                "capability_profile",
                "feature_vector",
                "player_attributes",
                "rating_presentation",
                "archetype_profile",
            ]
            for d in dicts:
                for key in complex_keys:
                    if d.get(key) and isinstance(d[key], str):
                        d[key] = json.loads(d[key])
            return [_player_adapter.validate_python(d) for d in dicts]
        except Exception as e:
            logger.error(f"Failed to retrieve all players: {e}")
            return []
        finally:
            con.close()

    def get_collective(self, team_id: int) -> CollectiveProfile | None:
        """Load Collective Profile from JSON store."""
        if not COLLECTIVE_PROFILES_PATH.exists():
            return None
        try:
            with open(COLLECTIVE_PROFILES_PATH) as f:
                collectives = json.load(f)
            for c in collectives:
                if c["team_id"] == team_id:
                    return _collective_adapter.validate_python(c)
            return None
        except Exception as e:
            logger.error(f"Failed to load collective profile for team {team_id}: {e}")
            return None

    def get_all_collectives(self) -> list[CollectiveProfile]:
        """Load all Collective Profiles."""
        if not COLLECTIVE_PROFILES_PATH.exists():
            return []
        try:
            with open(COLLECTIVE_PROFILES_PATH) as f:
                collectives = json.load(f)
            return [_collective_adapter.validate_python(c) for c in collectives]
        except Exception as e:
            logger.error(f"Failed to load collective profiles: {e}")
            return []
