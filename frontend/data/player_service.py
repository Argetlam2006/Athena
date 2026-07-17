"""
frontend/data/player_service.py — Frontend Data Service for Players.

Coordinates data access and intelligence algorithms for player-centric views.
"""

import logging

import pandas as pd
import streamlit as st

from backend.intelligence.decision import DecisionEngine
from backend.intelligence.store import IntelligenceStore
from shared.schemas import PlayerDecisionCard, PlayerProfile, ProfileType

logger = logging.getLogger(__name__)


@st.cache_data
def get_player_index() -> pd.DataFrame:
    store = IntelligenceStore()
    df = store.get_player_index()
    if df.empty:
        st.warning("Intelligence Store not found. Please run scripts/bootstrap.py.")
    return df


@st.cache_data
def get_player_profile(player_id: int) -> PlayerProfile | None:
    store = IntelligenceStore()
    return store.get_player(player_id)


@st.cache_data
def get_player_career(player_id: int) -> list[PlayerProfile]:
    store = IntelligenceStore()
    return store.get_player_career(player_id)


@st.cache_data
def get_players_by_position(
    position: str, profile_type: ProfileType = ProfileType.CAREER
) -> list[PlayerProfile]:
    store = IntelligenceStore()
    return store.get_players_by_position(position, profile_type)


@st.cache_data
def get_all_players(
    profile_type: ProfileType = ProfileType.CAREER,
) -> list[PlayerProfile]:
    store = IntelligenceStore()
    return store.get_all_players(profile_type)


def get_player_decision_card(player: PlayerProfile) -> PlayerDecisionCard:
    """Coordinates DecisionEngine to build a player decision card."""
    cohort = get_players_by_position(player.position_group, player.profile_type)
    return DecisionEngine.build_player_decision_card(player, cohort)
