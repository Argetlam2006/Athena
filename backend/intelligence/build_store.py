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
        vectors = map_player_summary_to_vectors(df)

        # 3. Process Intelligence
        logger.info(f"Computing Football Intelligence for {len(vectors)} players...")
        engine = FootballIntelligenceEngine()
        players = engine.process_cohort(vectors)

        logger.info("Computing Team Intelligence...")
        teams = engine.process_all_teams(players)

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
