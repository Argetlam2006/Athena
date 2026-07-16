"""
frontend/data/dashboard.py — Frontend Data Access for Dashboard.

Aggregates platform KPIs and health metrics.
"""

import streamlit as st

from frontend.data.players import get_player_index, get_player_profile
from frontend.data.teams import get_team_index, get_team_profile


@st.cache_data
def get_dashboard_summary() -> dict:
    """Retrieve global platform overview statistics."""
    player_idx = get_player_index()
    team_idx = get_team_index()

    featured_player = None
    if not player_idx.empty and len(player_idx) > 1:
        pid = int(player_idx.iloc[1]['player_id'])
        featured_player = get_player_profile(pid)

    featured_team = None
    if not team_idx.empty and len(team_idx) > 1:
        tid = int(team_idx.iloc[1]['team_id'])
        featured_team = get_team_profile(tid)

    from shared.schemas import ProfileType

    unique_players = player_idx['player_id'].nunique() if not player_idx.empty else 0
    career_profiles = len(player_idx[player_idx['profile_type'] == ProfileType.CAREER]) if not player_idx.empty else 0
    season_profiles = len(player_idx[player_idx['profile_type'] == ProfileType.SEASON]) if not player_idx.empty else 0
    competition_profiles = len(player_idx[player_idx['profile_type'] == ProfileType.COMPETITION]) if not player_idx.empty else 0

    return {
        "total_players": len(player_idx),
        "unique_players": unique_players,
        "career_profiles": career_profiles,
        "season_profiles": season_profiles,
        "competition_profiles": competition_profiles,
        "total_teams": len(team_idx),
        "total_leagues": player_idx[player_idx['profile_type'] == ProfileType.COMPETITION]['competition'].nunique() if not player_idx.empty else 0,
        "database_health": "Online",
        "last_updated": "Recently",
        "featured_player": featured_player,
        "featured_team": featured_team,
    }
