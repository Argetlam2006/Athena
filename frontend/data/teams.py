"""
frontend/data/teams.py — Frontend Data Access for Teams.

Retrieves and caches TeamProfile objects for the UI.
Delegates to backend services for the frontend shell.
"""

import logging

import pandas as pd
import streamlit as st

from backend.intelligence.store import IntelligenceStore
from shared.schemas import TeamProfile

logger = logging.getLogger(__name__)

@st.cache_data
def get_team_index() -> pd.DataFrame:
    store = IntelligenceStore()
    df = store.get_team_index()
    if df.empty:
        st.warning("Intelligence Store not found.")
    return df

@st.cache_data
def get_team_profile(team_id: int) -> TeamProfile | None:
    """Retrieve a specific TeamProfile lazily in O(1)."""
    store = IntelligenceStore()
    return store.get_team(team_id)

@st.cache_data
def get_all_teams() -> list[TeamProfile]:
    store = IntelligenceStore()
    return store.get_all_teams()
