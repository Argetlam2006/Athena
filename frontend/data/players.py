"""
frontend/data/players.py — Frontend Data Access for Players.

Retrieves and caches PlayerProfile objects for the UI.
Delegates to backend services for the frontend shell.
"""

import logging

import pandas as pd
import streamlit as st

from backend.intelligence.store import IntelligenceStore
from shared.schemas import PlayerProfile

logger = logging.getLogger(__name__)

@st.cache_data
def get_player_index() -> pd.DataFrame:
    """
    Load the lightweight player metadata index.
    Used for instantaneous UI search and discovery.
    """
    store = IntelligenceStore()
    df = store.get_player_index()
    if df.empty:
        st.warning("Intelligence Store not found. Please run scripts/bootstrap.py.")
    return df

@st.cache_data
def get_player_profile(player_id: int) -> PlayerProfile | None:
    """Retrieve a specific PlayerProfile lazily in O(1)."""
    store = IntelligenceStore()
    return store.get_player(player_id)

@st.cache_data
def get_players_by_position(position: str) -> list[PlayerProfile]:
    """
    Load profiles dynamically based on position to avoid full 22k memory loads.
    """
    import duckdb

    from backend.intelligence.store import PLAYER_PROFILES_PATH, _player_adapter

    if not PLAYER_PROFILES_PATH.exists():
        return []

    con = duckdb.connect(":memory:")
    try:
        query = f"SELECT * FROM read_parquet('{PLAYER_PROFILES_PATH}') WHERE position_group = ?"
        df = con.execute(query, [position]).fetchdf()
        if df.empty:
            return []
        dicts = df.to_dict(orient="records")
        return [_player_adapter.validate_python(d) for d in dicts]
    except Exception as e:
        logger.error(f"Failed to retrieve players for position {position}: {e}")
        return []
    finally:
        con.close()

@st.cache_data
def get_all_players() -> list[PlayerProfile]:
    """
    [DEVELOPER ONLY / DEBUGGING]
    Load all PlayerProfiles. Do not use in production UI.
    """
    import duckdb

    from backend.intelligence.store import PLAYER_PROFILES_PATH, _player_adapter

    if not PLAYER_PROFILES_PATH.exists():
        logger.warning("Intelligence Store not found.")
        st.warning("Data Warehouse not found. Please run scripts/bootstrap.py.")
        return []

    con = duckdb.connect(":memory:")
    try:
        df = con.execute(f"SELECT * FROM read_parquet('{PLAYER_PROFILES_PATH}')").fetchdf()
        if df.empty:
            return []
        dicts = df.to_dict(orient="records")
        return [_player_adapter.validate_python(d) for d in dicts]
    except Exception as e:
        logger.error(f"Failed to retrieve players: {e}", exc_info=True)
        st.error("Failed to load player intelligence profiles.")
        return []
    finally:
        con.close()
