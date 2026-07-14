# Athena Analytics Warehouse

## Overview

The Athena Analytics Warehouse is a **DuckDB-powered analytical layer** that sits directly on top of the Phase 2.1 Parquet files and serves as the **single source of truth** for all downstream analysis, the Decision Intelligence engine, the Streamlit UI, and the AI explanation layer.

---

## Why DuckDB

| Property | Benefit for Athena |
|---|---|
| **Columnar storage** | Aggregations over millions of events are O(columns), not O(rows) |
| **Zero-copy Parquet scanning** | `read_parquet()` doesn't load files into memory — queries scan directly |
| **Embedded** | No server, no configuration. One `.duckdb` file, zero infrastructure |
| **OLAP SQL** | `QUALIFY`, `FILTER`, `PERCENT_RANK`, `NTILE`, `STRUCT` — purpose-built for analytics |
| **Python-native** | `conn.execute(sql).df()` returns a pandas DataFrame — no ORM overhead |

Alternative considered: **PostgreSQL** (more familiar, heavier), **SQLite** (single-threaded, no window functions), **Polars** (great, but no persistent SQL catalog).

---

## Architecture

```
data/raw/*.json                   Phase 1: Ingestion (load_data.py)
        ↓
data/processed/*.parquet          Phase 2.1: ETL (normalize.py → pipeline.py)
        ↓   zero-copy via read_parquet()
data/warehouse/athena.duckdb      Phase 2.2: Analytics Warehouse
        ├── competitions           ← base view
        ├── matches                ← base view
        ├── events                 ← base view (primary analytical table)
        └── lineups                ← base view
                ↓   sql/views/*.sql
        ├── vw_match_summary
        ├── vw_player_summary
        ├── vw_team_summary
        ├── vw_player_percentiles
        └── vw_recruitment_candidates
                ↓   WarehouseQueries
        Analytics Engine / Streamlit UI / AI Explanation Layer
```

---

## Data Flow Through the Warehouse

### 1. Parquet Registration (Python)

`Warehouse._register_parquet()` creates DuckDB **views** over each Parquet file:

```sql
CREATE OR REPLACE VIEW events AS
SELECT * FROM read_parquet('/path/to/data/processed/events.parquet')
```

This is **zero-copy** — DuckDB scans the Parquet file lazily at query time. No data is loaded into memory until a query asks for it.

### 2. Analytical Views (SQL)

`Warehouse._create_views()` reads every `.sql` file in `sql/views/` in alphabetical order and executes it. Files are numbered (`01_`, `02_`, ...) to guarantee correct dependency order:

| Order | File | Depends On |
|---|---|---|
| 01 | `vw_match_summary` | `events`, `matches` |
| 02 | `vw_player_summary` | `events`, `lineups`, `matches` |
| 03 | `vw_team_summary` | `events`, `matches` |
| 04 | `vw_player_percentiles` | `vw_player_summary` |
| 05 | `vw_recruitment_candidates` | `vw_player_summary`, `vw_player_percentiles` |

### 3. Query Layer (Python)

`WarehouseQueries` exposes typed, parameterized methods. **No module outside `queries.py` writes a raw SQL string.**

```python
from backend.warehouse import Warehouse

wh = Warehouse().build()
df = wh.player_summary(competition="La Liga", min_matches=3)
df = wh.player_percentiles(position="Center Forward")
df = wh.recruitment_candidates(top_n=20)
```

---

## Analytical Views

### `vw_match_summary`

One row per match with derived analytics:

| Column | Type | Description |
|---|---|---|
| `result` | str | `Home Win`, `Away Win`, `Draw` |
| `match_classification` | str | `High Scoring` (≥4 goals), `Goalless`, `Normal` |
| `home_xg` / `away_xg` | float | xG from event aggregation |
| `xg_differential` | float | home_xg − away_xg (positive = home dominant) |
| `home_shot_share_pct` | float | Home team's percentage of total shots |
| `home_pass_accuracy_pct` | float | Accurate passes / total passes × 100 |

**SQL techniques:** conditional `FILTER` aggregation, `CASE` classification, `NULLIF` division guard, multi-CTE home/away pivot.

---

### `vw_player_summary`

One row per player per competition-season. The primary analytical view.

**Pass metrics:** `total_passes`, `accurate_passes`, `pass_accuracy_pct`, `avg_pass_length_m`, `progressive_passes`, `crosses`, `switches`, `through_balls`, `shot_assists`, `goal_assists`

**Shot metrics:** `total_shots`, `shots_on_target`, `shot_accuracy_pct`, `goals`, `xg_total`, `npxg_total`, `goals_minus_xg`, `xg_per_shot`

**Carry/Dribble:** `total_carries`, `total_carry_distance_m`, `progressive_carries`, `total_dribbles`, `dribbles_completed`, `dribble_success_pct`

**Per-90 metrics** (the standard unit for fair cross-player comparison): `goals_p90`, `xg_p90`, `npxg_p90`, `shots_p90`, `passes_p90`, `carries_p90`, `progressive_passes_p90`, `progressive_carries_p90`, `goal_assists_p90`

**SQL techniques:** 6-CTE pipeline (pass → shot → carry → dribble → pressure → appearances), `QUALIFY ROW_NUMBER()` for primary position, `NULLIF`-safe ratios, `COALESCE` on all LEFT JOIN aggregations.

> **Approximation:** `minutes_played = matches_played × 90`. Precise substitution tracking is Phase 3.

---

### `vw_team_summary`

One row per team per competition-season.

| Column | Description |
|---|---|
| `wins`, `draws`, `losses` | Season record via `FILTER` aggregation |
| `points` | Standard 3-1-0 system |
| `goals_scored`, `goals_conceded`, `goal_difference` | From matches table |
| `xg_for`, `xg_against`, `xg_difference` | xG from event aggregation (both perspectives) |
| `pass_accuracy_pct` | Accurate passes / total passes |
| `avg_xg_per_match` | xG created per game |

**SQL techniques:** `UNION ALL` to combine home/away records per team, `xg_against` derived by inverting the team perspective, `FILTER` for W/D/L counting.

---

### `vw_player_percentiles`

One row per player per competition-season. Percentile rankings for key metrics.

**Window functions used:**

| Column | Function | Scope |
|---|---|---|
| `xg_p90_pct_in_position` | `PERCENT_RANK()` | Within position |
| `goals_p90_pct_in_position` | `PERCENT_RANK()` | Within position |
| `pass_acc_pct_in_position` | `PERCENT_RANK()` | Within position |
| `dribble_pct_in_position` | `PERCENT_RANK()` | Within position |
| `prog_pass_pct_in_position` | `PERCENT_RANK()` | Within position |
| `xg_total_pct_overall` | `PERCENT_RANK()` | All players |
| `xg_decile` | `NTILE(10)` | All players |
| `xg_p90_decile_in_position` | `NTILE(10)` | Within position |
| `overall_percentile` | Weighted composite | — |

**Composite `overall_percentile`:**

```
overall_percentile =
  xg_p90_pct_in_position     × 0.35   (shot creation efficiency)
  + goals_p90_pct_in_position × 0.25   (direct goal output)
  + pass_acc_pct_in_position  × 0.20   (technical quality)
  + dribble_pct_in_position   × 0.20   (1v1 effectiveness)
```

---

### `vw_recruitment_candidates`

One row per player meeting quality thresholds (≥2 matches, ≥20 events).

**Contribution Score (0–100):**

```
contribution_score =
  xg_p90_pct    × 0.40   (shooting efficiency — primary weight)
  + goals_p90_pct × 0.25   (goal-scoring productivity)
  + pass_acc_pct  × 0.20   (passing quality)
  + prog_pass_pct × 0.15   (ability to advance play)
```

**Analytical flags** (used by the Decision Engine for narrative explanation):

| Flag | Condition |
|---|---|
| `is_clinical_finisher` | goals_minus_xg > 0 AND goals ≥ 2 |
| `is_high_volume_passer` | pass_acc_pct ≥ 60 AND passes_p90 ≥ 30 |
| `is_progressive_passer` | prog_pass_pct ≥ 65 |
| `is_progressive_carrier` | prog_carry_pct ≥ 65 |
| `is_elite_dribbler` | dribble_pct ≥ 70 AND dribble_success_pct ≥ 50 |
| `is_efficient_shooter` | xG per shot > 0.10 |

**SQL techniques:** JOIN across two views, `ROW_NUMBER()` within position, `COUNT(*) OVER` for pool size, `COALESCE` for missing percentiles, boolean flag derivation.

---

## Warehouse Lifecycle

```bash
# Step 1 — Fetch data
make data                    # 5 La Liga sample matches

# Step 2 — ETL (JSON → Parquet)
make etl                     # writes data/processed/*.parquet

# Step 3 — Build warehouse (Parquet → DuckDB views)
make warehouse               # writes data/warehouse/athena.duckdb

# Step 4 — Inspect
make warehouse-info          # lists all registered views

# Re-run after new data (idempotent)
make warehouse               # CREATE OR REPLACE VIEW — safe to re-run
```

---

## File Inventory

```
backend/warehouse/
  connection.py              — DuckDB context manager (connect())
  warehouse.py               — Warehouse class: build(), player_summary(), ...
  queries.py                 — WarehouseQueries: parameterized DataFrame methods
  __init__.py                — Public API: Warehouse, WarehouseQueries, connect

sql/views/
  01_vw_match_summary.sql    — Match overview with event aggregation
  02_vw_player_summary.sql   — Player stats (6 CTEs, per-90s, ratios)
  03_vw_team_summary.sql     — Team W/D/L, points, xG, passing
  04_vw_player_percentiles.sql — PERCENT_RANK, NTILE window functions
  05_vw_recruitment_candidates.sql — Composite scoring, position ranking

tests/
  test_warehouse.py          — 51 tests, all in-memory DuckDB
```

---

## Python Quick Reference

```python
from backend.warehouse import Warehouse

# Build the warehouse (idempotent)
wh = Warehouse().build()

# Query all views
df_matches  = wh.match_summary(competition="La Liga")
df_players  = wh.player_summary(min_matches=3, position="Center Forward")
df_teams    = wh.team_summary(competition="La Liga")
df_pct      = wh.player_percentiles(min_matches=3)
df_recruit  = wh.recruitment_candidates(top_n=20)

# Access the full query interface
from backend.warehouse.connection import connect
from backend.warehouse.queries import WarehouseQueries

with connect() as conn:
    q = WarehouseQueries(conn)
    df = q.get_player_by_id(5503)       # Messi
    df = q.execute("SELECT ...")         # ad-hoc (stays in queries.py)
    views = q.list_views()              # introspect
```
