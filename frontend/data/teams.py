"""
frontend/data/teams.py — Frontend Data Access for Teams.

Retrieves and caches TeamProfile objects for the UI.
Delegates to backend services for the frontend shell.
"""

import logging
import streamlit as st
import pandas as pd

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
    import json
    from backend.intelligence.store import TEAM_PROFILES_PATH, _team_adapter
    
    json_path = TEAM_PROFILES_PATH.with_suffix(".json")
    if not json_path.exists():
        return []
        
    try:
        with open(json_path, "r") as f:
            teams = json.load(f)
        return [_team_adapter.validate_python(t) for t in teams]
    except Exception as e:
        logger.error(f"Failed to load teams: {e}")
        return []
