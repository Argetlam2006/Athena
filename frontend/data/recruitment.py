"""
frontend/data/recruitment.py — Frontend Data Access for Recruitment.

Executes recruitment queries using the Decision Intelligence Engine.
"""

import streamlit as st

from backend.recommendation.engine import DecisionIntelligenceEngine
from frontend.data.players import get_all_players, get_players_by_position
from shared.schemas import RecruitmentCandidate, RecruitmentCriteria


@st.cache_data
def search_candidates(criteria: RecruitmentCriteria) -> list[RecruitmentCandidate]:
    """
    Search and rank candidates based on criteria.
    Uses the DecisionIntelligenceEngine on the subset of players matching the position.
    """
    if criteria.position:
        pool = get_players_by_position(criteria.position)
    else:
        # Fallback for debugging/CLI usage if no position is specified
        pool = get_all_players()
        
    engine = DecisionIntelligenceEngine()

    return engine.rank_candidates(pool, criteria)
