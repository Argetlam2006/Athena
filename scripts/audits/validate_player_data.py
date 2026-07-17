import os
import sys

import duckdb
import pandas as pd
from pydantic import TypeAdapter

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.intelligence.adapter import map_player_summary_to_vectors
from backend.intelligence.store import IntelligenceStore


def trace_player(player_name: str):
    print("========================================================")
    print(f"TRACING PLAYER: {player_name}")
    print("========================================================")

    db_path = "data/warehouse/athena.duckdb"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    con = duckdb.connect(db_path, read_only=True)

    # 1. DuckDB Warehouse View
    name_parts = player_name.split()
    last_name = name_parts[-1]
    query = f"SELECT * FROM vw_player_summary WHERE player_name ILIKE '%{last_name}%'"
    df = con.execute(query).fetchdf()

    if df.empty:
        print("Not found in vw_player_summary.")
        return

    # We will trace the first match
    row = df.iloc[0]
    print("--- 1. DuckDB Warehouse (vw_player_summary) ---")
    print(f"Matches: {row.get('matches_played')}")
    print(f"Minutes: {row.get('minutes_played')}")
    print(f"Birth Date: {row.get('birth_date')}")
    print(f"Goals: {row.get('goals')}")
    print(f"Assists: {row.get('goal_assists')}")
    print(f"xG: {row.get('xg_total')}")

    # 2. PlayerFeatureVector
    # We map just this row to a vector
    vectors = map_player_summary_to_vectors(pd.DataFrame([row]))
    if not vectors:
        print("Failed to map to vector.")
        return
    vector = vectors[0]
    print("\n--- 2. PlayerFeatureVector ---")
    print(f"Matches: {vector.matches_played}")
    print(f"Minutes: {vector.minutes_played}")
    print(f"Birth Date: {vector.birth_date}")
    print(f"Goals p90: {vector.goals_p90}")
    print(f"Assists p90: {vector.goal_assists_p90}")
    print(f"npxG p90: {vector.npxg_p90}")

    # 3. PlayerProfile
    print("\n--- 3. PlayerProfile (from Intelligence Store) ---")
    store = IntelligenceStore()
    if not store.is_valid():
        print("Intelligence Store is invalid/missing.")

    # Manual load to bypass lazy loading if needed, but get_player works
    from frontend.data.players import get_player_profile

    profile = get_player_profile(vector.player_id)
    if not profile:
        print("Profile not found in store.")
        return

    print(
        f"Matches: {profile.feature_vector.matches_played if profile.feature_vector else 'N/A'}"
    )
    print(
        f"Minutes: {profile.feature_vector.minutes_played if profile.feature_vector else 'N/A'}"
    )
    print(f"Birth Date: {profile.birth_date}")
    print(f"Age Years: {profile.age_years}")

    print("\n--- 4. Frontend Serialization (Pydantic Dump) ---")
    adapter = TypeAdapter(type(profile))
    dump = adapter.dump_python(profile)
    fv = dump.get("feature_vector", {})
    print(f"Matches: {fv.get('matches_played')}")
    print(f"Minutes: {fv.get('minutes_played')}")
    print(f"Birth Date: {dump.get('birth_date')}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_player_data.py <player_name>...")
        sys.exit(1)

    for name in sys.argv[1:]:
        trace_player(name)
        print("\n")
