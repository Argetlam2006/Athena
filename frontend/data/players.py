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
def get_player_career(player_id: int) -> list[PlayerProfile]:
    """Retrieve all available profiles for a player."""
    store = IntelligenceStore()
    return store.get_player_career(player_id)

@st.cache_data
def get_players_by_position(position: str) -> list[PlayerProfile]:
    """
    Load profiles dynamically based on position to avoid full 22k memory loads.
    """
    store = IntelligenceStore()
    return store.get_players_by_position(position)

@st.cache_data
def get_all_players() -> list[PlayerProfile]:
    """
    [DEVELOPER ONLY / DEBUGGING]
    Load all PlayerProfiles. Do not use in production UI.
    """
    store = IntelligenceStore()
    return store.get_all_players()
