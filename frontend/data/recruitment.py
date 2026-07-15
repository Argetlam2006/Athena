"""
frontend/data/recruitment.py — Frontend Data Access for Recruitment.

Executes recruitment queries using the Decision Intelligence Engine.
"""

import streamlit as st

from backend.recommendation.engine import DecisionIntelligenceEngine
from frontend.data.players import get_all_players
from shared.schemas import RecruitmentCandidate, RecruitmentCriteria


@st.cache_data
def search_candidates(criteria: RecruitmentCriteria) -> list[RecruitmentCandidate]:
    """
    Search and rank candidates based on criteria.
    Uses the DecisionIntelligenceEngine on the mocked pool.
    """
    pool = get_all_players()
    engine = DecisionIntelligenceEngine()

    # We must construct a real RecruitmentCriteria object since Streamlit might hash it.
    # Actually criteria is already the object.

    return engine.rank_candidates(pool, criteria)
