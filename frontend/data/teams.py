"""
frontend/data/teams.py — Frontend Data Access for Teams.

Retrieves and caches TeamProfile objects for the UI.
"""

import streamlit as st
from shared.schemas import TeamProfile
from frontend.data.players import get_all_players


@st.cache_data
def _get_mock_teams() -> list[TeamProfile]:
    """Generates mock teams based on the mock players."""
    all_players = get_all_players()
    
    psg_players = [p for p in all_players if p.team_name == "Paris Saint-Germain"]
    mci_players = [p for p in all_players if p.team_name == "Manchester City"]
    
    t1 = TeamProfile(
        team_id=101, team_name="Paris Saint-Germain", competition="Ligue 1", season="2023",
        squad_size=len(psg_players), average_age=29.5, style_label="Direct and Progressive",
        capability_profile=None # Mocking requires aggregation, we leave this None for empty state tests
    )
    
    t2 = TeamProfile(
        team_id=102, team_name="Manchester City", competition="Premier League", season="2023",
        squad_size=len(mci_players), average_age=24.0, style_label="Possession-Dominant",
        capability_profile=None
    )
    
    return [t1, t2]


@st.cache_data
def get_all_teams() -> list[TeamProfile]:
    """Retrieve all available teams."""
    return _get_mock_teams()


@st.cache_data
def get_team_profile(team_id: int) -> TeamProfile | None:
    """Retrieve a specific TeamProfile by ID."""
    for t in get_all_teams():
        if t.team_id == team_id:
            return t
    return None
