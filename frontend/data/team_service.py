"""
frontend/data/team_service.py — Frontend Data Service for Teams.

Coordinates data access and intelligence algorithms for team-centric views.
"""

import logging

import pandas as pd
import streamlit as st

from backend.intelligence.decision import DecisionEngine
from backend.intelligence.store import IntelligenceStore
from frontend.data.player_service import get_all_players
from shared.schemas import CollectiveProfile, TeamDecisionCard

logger = logging.getLogger(__name__)


@st.cache_data
def get_collective_index() -> pd.DataFrame:
    store = IntelligenceStore()
    collectives = store.get_all_collectives()
    if not collectives:
        st.warning("Intelligence Store missing collectives. Please run pipeline.")
        return pd.DataFrame()

    data = []
    for t in collectives:
        data.append(
            {
                "team_id": t.team_id,
                "team_name": t.team_name,
                "competition": t.competition,
                "season": t.season,
            }
        )
    return pd.DataFrame(data)


@st.cache_data
def get_collective_profile(team_id: int) -> CollectiveProfile | None:
    store = IntelligenceStore()
    return store.get_collective(team_id)


@st.cache_data
def get_all_collectives() -> list[CollectiveProfile]:
    store = IntelligenceStore()
    return store.get_all_collectives()


def get_team_decision_card(team: CollectiveProfile) -> TeamDecisionCard:
    """Coordinates DecisionEngine to build a team decision card."""
    from shared.schemas import ProfileType

    all_players = get_all_players(ProfileType.COMPETITION)
    squad = [
        p
        for p in all_players
        if p.team_name == team.team_name
        and p.competition == team.competition
        and p.season == team.season
    ]
    cohort_teams = [
        t
        for t in get_all_collectives()
        if t.competition == team.competition and t.season == team.season
    ]
    return DecisionEngine.build_team_decision_card(team, squad, cohort_teams)
