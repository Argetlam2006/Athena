# Athena Roadmap

> AI-powered Football Decision Intelligence Platform

---

## Current Status

**Version 1 — In Development**

Sprint 0 in progress: Repository Setup & Landing Page

---

## Version 1 — Foundation (Current)

Version 1 establishes the complete Football Decision Intelligence workflow
across five analytical workspaces.

### Sprint 0 — Repository Setup ✅
- [x] Repository structure
- [x] Python environment (pyproject.toml, requirements.txt, Makefile)
- [x] Shared schemas, constants and models
- [x] Data acquisition infrastructure
- [x] Streamlit landing page

### Sprint 1 — Data Engineering 🔄
- [ ] StatsBomb Open Data ingestion
- [ ] Data validation framework
- [ ] ETL pipeline (clean → normalize → Parquet)
- [ ] DuckDB warehouse loading

### Sprint 2 — Analytics Warehouse
- [ ] Dimensional star schema (dim_player, dim_team, fact_events…)
- [ ] SQL analytical views (vw_player_summary, vw_team_style…)
- [ ] Feature store construction
- [ ] Materialized views for performance

### Sprint 3 — Analytics Engine
- [ ] Per-90 feature engineering
- [ ] Position and league normalization
- [ ] Percentile ranking
- [ ] **Athena Intelligence Framework** — 8 capability scores:
  - Ball Progression
  - Chance Creation
  - Ball Security
  - Press Resistance
  - Defensive Activity
  - Attacking Threat
  - Physical Availability
  - Tactical Versatility
- [ ] Player Intelligence profiles
- [ ] Team Intelligence profiles

### Sprint 4 — Machine Learning
- [ ] Cosine similarity engine (similar player search)
- [ ] Nearest-neighbour recommendation ranking
- [ ] Rule-based player archetype classification

### Sprint 5 — Decision Engine
- [ ] Recruitment Engine (filter → rank → recommend)
- [ ] Comparison Engine (multi-player comparison)
- [ ] Evidence generation for every recommendation

### Sprint 6 — User Interface
- [ ] Executive Dashboard
- [ ] Player Intelligence workspace
- [ ] Team Intelligence workspace
- [ ] Recruitment Intelligence workspace
- [ ] Ask Athena (conversational interface)

### Sprint 7 — AI Layer
- [ ] Structured prompt engineering
- [ ] Player scouting report generator
- [ ] Team report generator
- [ ] Recruitment report generator
- [ ] PDF export

### Sprint 8 — Testing
- [ ] Unit tests (analytics, capability, similarity)
- [ ] Integration tests (ETL, warehouse, pipeline)
- [ ] End-to-end tests (full workflow)

### Sprint 9 — Polish & Deployment
- [ ] UX improvements
- [ ] Performance optimization (DuckDB indexes, caching)
- [ ] Full documentation
- [ ] Streamlit Community Cloud deployment

---

## Version 2 — Extended Intelligence (Planned)

Version 2 extends the same intelligence framework into additional football
domains without changing the underlying architecture.

| Module | Focus Question |
|--------|---------------|
| Opponent Intelligence | How does our next opponent play? |
| Match Intelligence | What happened in this match? |
| Academy Intelligence | Which youth players are developing fastest? |
| Contract Intelligence | Which contracts represent the best value? |

### Data Expansion
- FBref integration (season statistics)
- Transfermarkt integration (market values, contracts)
- Multi-provider entity resolution (unified player IDs)

### Infrastructure Expansion
- Cloud deployment (AWS / GCP)
- Streaming data pipelines
- Authentication and multi-user support

---

## Version 3 — Live Intelligence (Future)

| Capability | Description |
|-----------|-------------|
| Live Match Analytics | Real-time event processing |
| Tracking Data | Player movement and positioning |
| Video Analytics | AI-powered video tagging |
| Wearable Integration | Training load and injury risk |

---

## Technical Principles (All Versions)

These principles apply regardless of version.

> Every recommendation must be traceable from event → statistic → capability → intelligence → decision → explanation.

- Explainability over black-box accuracy
- Evidence before AI
- No recommendation without supporting data
- Clean, readable, modular code

---

## Architecture Decisions Log

Significant decisions are recorded in `docs/ARCHITECTURE_DECISIONS.md`.

---

*Roadmap subject to change. All decisions recorded with rationale.*
