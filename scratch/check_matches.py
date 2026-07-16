import duckdb

con = duckdb.connect('data/warehouse/athena.duckdb', read_only=True)
df = con.execute("SELECT season_name, matches_played FROM vw_player_summary WHERE player_name ILIKE '%Messi%'").fetchdf()
print(df)
