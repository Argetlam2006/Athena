"""
frontend/data/recruitment_service.py — Frontend Data Service for Recruitment.

Coordinates data access and intelligence algorithms for candidate evaluation.
"""

import streamlit as st

from backend.recommendation.engine import DecisionIntelligenceEngine
from frontend.data.player_service import get_all_players, get_players_by_position
from shared.constants import BROAD_POSITION_MAP
from shared.schemas import RecruitmentCandidate, RecruitmentCriteria


@st.cache_data
def search_candidates(criteria: RecruitmentCriteria) -> list[RecruitmentCandidate]:
    """
    Search and rank candidates based on criteria.
    Coordinates RecommendationEngine on the subset of players matching the position.
    """
    if criteria.position and criteria.position in BROAD_POSITION_MAP:
        pool = []
        for specific_pos in BROAD_POSITION_MAP[criteria.position]:
            pool.extend(get_players_by_position(specific_pos))
    elif criteria.position:
        pool = get_players_by_position(criteria.position)
    else:
        pool = get_all_players()

    engine = DecisionIntelligenceEngine()
    return engine.rank_candidates(pool, criteria)
