# Athena — Architecture Decisions

This document records all significant architectural decisions made during
the implementation of Athena Version 1.

Each decision follows the format:
- **Decision**: What was decided
- **Status**: Accepted / Superseded / Deprecated
- **Context**: Why a decision was needed
- **Rationale**: Why this option was chosen
- **Alternatives Considered**: What else was evaluated
- **Consequences**: Trade-offs introduced

---

## ADR-001 — DuckDB over PostgreSQL

**Date**: 2026-07-14
**Status**: Accepted

### Decision

Athena uses **DuckDB + Parquet** as the analytics warehouse instead of PostgreSQL.

### Context

`03_TECH_SPEC.md` and `04_DATA_ARCHITECTURE.md` specify PostgreSQL as the
warehouse engine. `AGENTS.md` specifies DuckDB + Parquet. These two choices
are mutually exclusive and needed explicit resolution.

### Rationale

| Factor | PostgreSQL | DuckDB + Parquet |
|--------|-----------|-----------------|
| Setup | Requires server installation and configuration | Zero setup — in-process library |
| Portfolio deployment | Requires hosted DB (Render, Supabase) | Ships with the repo — works on Streamlit Cloud |
| Analytical performance | Good with indexes | Excellent — columnar, vectorized |
| SQL capability | Full PostgreSQL | Nearly full SQL, window functions, CTEs |
| Parquet compatibility | External tooling needed | Native first-class |
| Reproducibility | Depends on external server state | Warehouse = files in repo |

DuckDB satisfies all of `04_DATA_ARCHITECTURE.md`'s requirements:
- Dimensional star schema ✓
- SQL views and materialized views ✓
- Window functions, CTEs, analytical ranking ✓
- Indexes ✓
- Feature store ✓

### Alternatives Considered

1. **PostgreSQL** (as specified in 03_TECH_SPEC, 04_DATA_ARCHITECTURE): Rejected
   because it requires external infrastructure that complicates both local
   development and Streamlit Community Cloud deployment.

2. **SQLite**: Rejected because it lacks window functions and analytical
   aggregations needed for the feature engineering pipeline.

3. **Hybrid (DuckDB for analytics + PostgreSQL for API)**: Rejected as
   unnecessarily complex for a V1 portfolio project.

### Consequences

- ✓ Zero-configuration setup: `make setup && make data` is sufficient
- ✓ Warehouse is portable — `.duckdb` file travels with the repo
- ✓ Parquet files can be committed for offline demonstration
- ⚠ No concurrent write access from multiple processes (acceptable for V1)
- ⚠ DuckDB is less well-known in enterprise settings than PostgreSQL

---

## ADR-002 — Rule-Based Archetypes over K-Means Clustering

**Date**: 2026-07-14
**Status**: Accepted

### Decision

Player archetype classification uses **rule-based logic** derived from
capability scores, not K-Means clustering.

### Context

`IMPLEMENTATION_TASKS.md` (Task 4.2) specifies K-Means clustering.
`AGENTS.md` explicitly prohibits K-Means.

### Rationale

Athena's core principle is explainability. K-Means assigns clusters
probabilistically — a player's archetype emerges from an opaque distance
computation in N-dimensional space. This cannot be explained to a
sporting director.

Rule-based archetypes are transparent:
> *"This player is classified as a Ball-Playing Deep Midfielder because their
> Ball Progression score (87) exceeds 80 and their Defensive Activity score
> (73) exceeds 65."*

This reasoning is auditable, adjustable, and meaningful to football
professionals.

### Alternatives Considered

1. **K-Means** (as in IMPLEMENTATION_TASKS.md): Rejected — violates AIF
   explainability principle and AGENTS.md prohibition.

2. **DBSCAN**: Rejected — same explainability problem as K-Means.

3. **Hierarchical Clustering**: Rejected — same issue.

### Consequences

- ✓ Every archetype assignment is fully explainable
- ✓ Domain experts can tune archetype thresholds
- ✓ Consistent with AIF philosophy
- ⚠ Requires football domain knowledge to define archetype rules
- ⚠ May miss emergent player types that don't fit predefined archetypes

---

## ADR-003 — StatsBomb Open Data Only for Version 1

**Date**: 2026-07-14
**Status**: Accepted

### Decision

Version 1 uses **StatsBomb Open Data exclusively**. FBref and Transfermarkt
integration is deferred to Version 2.

### Context

`01_PRD.md` and `IMPLEMENTATION_TASKS.md` reference FBref and Transfermarkt
as data sources and include entity resolution (Task 1.4). `AGENTS.md`
explicitly restricts V1 to StatsBomb only.

### Rationale

Multi-provider integration requires:
1. Entity resolution (mapping player names across providers)
2. Schema harmonization (each provider uses different schemas)
3. Handling of missing data (a player may exist in StatsBomb but not FBref)

This complexity is out of scope for V1. StatsBomb Open Data is sufficient
to demonstrate the complete AIF pipeline with rich event-level detail.

### Consequences

- ✓ ETL pipeline is simpler and more reliable
- ✓ Entity resolution complexity eliminated for V1
- ✓ All data is CC BY-SA 4.0 — free to use and redistribute
- ⚠ Market value data unavailable (Tactical Versatility replaces Financial Value)
- ⚠ Limited to StatsBomb's covered competitions

---

## ADR-004 — Tactical Versatility Replaces Financial Value

**Date**: 2026-07-14
**Status**: Accepted

### Decision

The 8th capability is **Tactical Versatility** rather than Financial Value.

### Context

Financial Value (Market Value + Age + Contract) requires Transfermarkt data,
which is excluded from V1 (see ADR-003). The capability slot cannot remain
empty as the AIF defines exactly 8 capabilities.

Tactical Versatility is derivable from StatsBomb data:
- Positions played (distinct position records per player)
- Time distribution across positions
- Formation appearances count
- Performance consistency across roles

### Rationale

Tactical Versatility is analytically meaningful:
- Genuinely relevant to recruitment (can this player play multiple roles?)
- Derivable from StatsBomb's positional data
- Differentiates players in ways pure performance metrics miss
- Can be retained in V2 alongside a restored Financial Value capability

### Consequences

- ✓ All 8 capabilities derivable from StatsBomb Open Data
- ✓ Richer analytical story (versatility is genuinely useful for recruitment)
- ⚠ No financial analysis in V1 (market value, transfer cost)
- ⚠ Financial Value can be added in V2 without architectural changes

---

## ADR-005 — Shared Module for Cross-Cutting Definitions

**Date**: 2026-07-14
**Status**: Accepted

### Decision

A `shared/` top-level package contains all cross-cutting definitions:
- `shared/constants.py` — capability names, metric mappings, thresholds
- `shared/schemas.py` — typed dataclasses for AIF layer contracts
- `shared/models.py` — Pydantic models for the API layer

### Context

Without a canonical location, capability names and metric mappings would be
redefined in multiple modules, making updates error-prone.

### Rationale

A single source of truth prevents definition drift. If a capability name
changes, only `shared/constants.py` needs updating — all modules that
import from it automatically receive the update.

### Consequences

- ✓ Single source of truth for all AIF definitions
- ✓ Module coupling is explicit (imports show dependencies)
- ✓ `tests/test_constants.py` acts as a contract guard
- ⚠ All modules depend on `shared/` — changes require careful consideration
