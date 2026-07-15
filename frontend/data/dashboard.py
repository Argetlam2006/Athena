"""
frontend/data/dashboard.py — Frontend Data Access for Dashboard.

Aggregates platform KPIs and health metrics.
"""

import streamlit as st

from frontend.data.players import get_all_players
from frontend.data.teams import get_all_teams


@st.cache_data
def get_dashboard_summary() -> dict:
    """Retrieve global platform overview statistics."""
    players = get_all_players()
    teams = get_all_teams()

    return {
        "total_players": len(players),
        "total_teams": len(teams),
        "total_leagues": 2,
        "database_health": "Online",
        "last_updated": "2 hours ago",
        "featured_player": players[1] if len(players) > 1 else None,
        "featured_team": teams[1] if len(teams) > 1 else None,
    }
