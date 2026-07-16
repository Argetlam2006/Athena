import duckdb
import pandas as pd

con = duckdb.connect('data/warehouse/athena.duckdb')
df = con.execute("SELECT birth_date FROM vw_player_summary WHERE player_name LIKE '%Messi%'").fetchdf()
val = df.iloc[0]['birth_date']
print(repr(val), type(val), pd.notna(val))
if pd.notna(val):
    print(str(val).split(' ')[0])
