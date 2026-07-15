"""
frontend/data/players.py — Frontend Data Access for Players.

Retrieves and caches PlayerProfile objects for the UI.
Delegates to backend services for the frontend shell.
"""

import logging

import streamlit as st

from backend.intelligence.adapter import map_player_summary_to_vectors
from backend.intelligence.engine import FootballIntelligenceEngine
from backend.warehouse.warehouse import Warehouse
from shared.schemas import PlayerProfile

logger = logging.getLogger(__name__)

@st.cache_data
def get_all_players() -> list[PlayerProfile]:
    """
    Retrieve all players dynamically from the warehouse and generate their
    intelligence profiles.
    """
    try:
        # Initialize warehouse and retrieve player summary DataFrame
        wh = Warehouse().build()
        df = wh.query.get_player_summary()

        # Adapt raw DataFrame rows into strongly typed vectors
        vectors = map_player_summary_to_vectors(df)

        # Run intelligence engine to compute percentiles and assign archetypes
        engine = FootballIntelligenceEngine()
        profiles = engine.process_cohort(vectors)

        return profiles
    except FileNotFoundError:
        # Graceful degradation if warehouse hasn't been built yet
        logger.warning("Warehouse not found. Returning empty player list.")
        st.warning("Data Warehouse not found. Please run `make data` or ingest data first.")
        return []
    except Exception as e:
        logger.error(f"Failed to retrieve players: {e}", exc_info=True)
        st.error("Failed to load player intelligence profiles.")
        return []


@st.cache_data
def get_player_profile(player_id: int) -> PlayerProfile | None:
    """Retrieve a specific PlayerProfile by ID."""
    for p in get_all_players():
        if p.player_id == player_id:
            return p
    return None
