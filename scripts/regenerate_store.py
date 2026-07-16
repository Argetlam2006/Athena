import logging
from collections import defaultdict

from backend.intelligence.adapter import map_player_summary_to_vectors
from backend.intelligence.career import CareerBuilder
from backend.intelligence.engine import FootballIntelligenceEngine
from backend.intelligence.season import SeasonBuilder
from backend.intelligence.store import IntelligenceStore
from backend.warehouse.connection import connect

logging.basicConfig(level=logging.INFO)

def main():
    with connect() as db_conn:
        df_players = db_conn.execute("SELECT * FROM vw_player_summary").fetchdf()

    print(f"Loaded {len(df_players)} rows from vw_player_summary")

    # Run 1: Competition Profiles
    competition_vectors = map_player_summary_to_vectors(df_players)
    engine = FootballIntelligenceEngine(competition_matches=38)
    competition_profiles = engine.process_cohort(competition_vectors)

    # Group competition vectors by player_id and season
    player_season_comps = defaultdict(list)
    for v in competition_vectors:
        player_season_comps[(v.player_id, v.season)].append(v)

    # Build Season Vectors
    season_vectors = []
    for (pid, season), comps in player_season_comps.items():
        try:
            season_vectors.append(SeasonBuilder.build_season_vector(comps))
        except Exception as e:
            logging.warning(f"Failed to build season for player {pid} in {season}: {e}")

    # Run 2: Season Profiles
    season_profiles = engine.process_cohort(season_vectors)

    # Group season vectors by player_id
    player_seasons = defaultdict(list)
    for v in season_vectors:
        player_seasons[v.player_id].append(v)

    # Build Career Vectors
    career_vectors = []
    for pid, seasons in player_seasons.items():
        try:
            career_vectors.append(CareerBuilder.build_career_vector(seasons))
        except Exception as e:
            logging.warning(f"Failed to build career for player {pid}: {e}")

    # Run 3: Career Profiles
    career_profiles = engine.process_cohort(career_vectors)

    # Combine and save
    all_profiles = competition_profiles + season_profiles + career_profiles

    # Teams are built from competition profiles (or season, they are basically the same for team aggregation, but let's use competition to capture all matches precisely, wait, previously it used season_profiles (which were competition profiles)).
    team_profiles = engine.process_all_teams(competition_profiles)

    store = IntelligenceStore()
    store.save(all_profiles, team_profiles)

    print(f"Intelligence Store regenerated successfully with {len(competition_profiles)} competition, {len(season_profiles)} season, and {len(career_profiles)} career profiles.")

if __name__ == "__main__":
    main()
