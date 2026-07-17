"""
backend/intelligence/build_store.py — Intelligence Store Builder CLI.

Generates the Intelligence Store (player_profiles.parquet, team_profiles.parquet)
by running the Football Intelligence Engine over the entire DuckDB warehouse.
"""

import sys

from backend.intelligence.adapter import map_player_summary_to_vectors
from backend.intelligence.engine import FootballIntelligenceEngine
from backend.intelligence.store import IntelligenceStore
from backend.utils.logger import get_logger
from backend.warehouse.warehouse import Warehouse

logger = get_logger(__name__)

def main() -> int:
    try:
        logger.info("Starting Intelligence Store generation...")

        # 1. Initialize Warehouse and Store
        wh = Warehouse()
        store = IntelligenceStore()

        force = "--force" in sys.argv
        if not force and store.is_valid():
            logger.info("Intelligence Store is already up to date with the warehouse. Skipping.")
            return 0

        # 2. Extract Vectors
        logger.info("Extracting vectors from Warehouse...")
        df = wh.query.get_player_summary()
        comp_vectors = map_player_summary_to_vectors(df)

        from backend.intelligence.season import SeasonBuilder
        from backend.intelligence.career import CareerBuilder
        from collections import defaultdict
        from shared.schemas import ProfileType

        # ARCHITECTURAL INVARIANT: SINGLE SOURCE OF TRUTH PIPELINE
        # Competition Profiles -> SeasonBuilder -> Season Profiles -> CareerBuilder -> Career Profiles
        # This deterministic pipeline must never be bypassed.
        
        # 2a. Aggregate Competition vectors into Season vectors
        season_groups = defaultdict(list)
        for v in comp_vectors:
            season_groups[(v.player_id, v.season)].append(v)
            
        season_vectors = []
        for comps in season_groups.values():
            season_vectors.append(SeasonBuilder.build_season_vector(comps))
            
        # 2b. Aggregate Season vectors into Career vectors
        career_groups = defaultdict(list)
        for v in season_vectors:
            career_groups[v.player_id].append(v)
            
        career_vectors = []
        for seasons in career_groups.values():
            career_vectors.append(CareerBuilder.build_career_vector(seasons))
            
        vectors = comp_vectors + season_vectors + career_vectors

        # 3. Process Intelligence
        logger.info(f"Computing Football Intelligence for {len(vectors)} players...")
        engine = FootballIntelligenceEngine()
        players = engine.process_cohort(vectors)

        logger.info("Computing Team Intelligence...")
        comp_players = [p for p in players if p.profile_type == ProfileType.COMPETITION]
        teams = engine.process_all_teams(comp_players)

        # 4. Save Store
        logger.info("Serializing profiles to Intelligence Store...")
        store.save(players, teams)

        logger.info("Intelligence Store generation complete.")
        return 0

    except Exception as e:
        logger.error(f"Intelligence Store generation failed: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
