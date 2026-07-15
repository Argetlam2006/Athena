"""
frontend/data/teams.py — Frontend Data Access for Teams.

Retrieves and caches TeamProfile objects for the UI.
Delegates to backend services for the frontend shell.
"""

import streamlit as st

from backend.intelligence.engine import FootballIntelligenceEngine
from frontend.data.players import get_all_players
from shared.schemas import TeamProfile


@st.cache_data
def get_all_teams() -> list[TeamProfile]:
    """Retrieve all teams by dynamically grouping players."""
    players = get_all_players()
    engine = FootballIntelligenceEngine()
    teams = engine.process_all_teams(players)
    return teams


@st.cache_data
def get_team_profile(team_id: int) -> TeamProfile | None:
    """Retrieve a specific TeamProfile by ID."""
    for t in get_all_teams():
        if t.team_id == team_id:
            return t
    return None
