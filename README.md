# Athena

Athena is a production-quality, deterministic football intelligence platform. It bridges the gap between raw match event data and advanced sporting analytics by employing strict, mathematical reasoning models over which artificial intelligence acts strictly as an explanation layer. Athena is designed to empower analysts, sporting directors, and scouts with transparent, reproducible, and explainable football intelligence.

---

## Why Athena?

**The Problem**
Traditional football analytics dashboards often suffer from two extremes: they are either overwhelming grids of raw, uninterpreted numbers that require a trained data scientist to parse, or they are impenetrable "black-box" models (including raw LLMs) that hallucinate insights, invent statistics, and fail to provide deterministic proof for their claims.

**The "Evidence Before AI" Philosophy**
Athena rejects both paradigms. Its core philosophy is **"Evidence Before AI"**. 
Athena forces AI to act strictly as an *explanation layer* on top of a rigorously validated, deterministic **Football Intelligence Engine**. The system mathematically calculates all capabilities, percentiles, and match compatibilities internally. The AI sandbox is then provided with structured, immutable `EvidencePackets`. It cannot invent numbers; it can only narrate the deterministic evidence produced by the python backend.

---

## Quick Start

Athena requires exactly one command to build its entire intelligence store from scratch.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Argetlam2006/Athena.git
   cd Athena
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Bootstrap the data pipeline:**
   ```bash
   python scripts/maintenance/bootstrap.py
   ```
   *Note: This command downloads the StatsBomb Open Data, runs the ETL pipeline, builds the analytics warehouse, and generates the canonical Intelligence Store. The first run will take several minutes. You only need to run this once, or whenever the underlying dataset changes.*

4. **Launch Athena:**
   ```bash
   streamlit run frontend/app.py
   ```

5. **Run the test suite:**
   ```bash
   pytest
   ```

---
## Core Capabilities

- **Football Intelligence Engine (FIE)**: Synthesizes raw event data into canonical capability scores and percentiles.
- **Collective Intelligence Engine (CIE)**: Aggregates individual player metrics to form cohesive team profiles and identify tactical styles.
- **Decision Intelligence**: Produces deterministic reasoning (Player and Team Decision Cards) highlighting elite traits, weak areas, and dependencies.
- **Recruitment Intelligence**: A semantic player search engine utilizing deterministic fit-scoring algorithms based on required capabilities.
- **Counterfactual Engine**: Analyzes "what-if" scenarios, such as the impact on a team's tactical identity if a key player is replaced.
- **Explainability Engine**: Translates mathematical vectors into strictly controlled, highly contextual `EvidencePackets` for LLM consumption.
- **Ask Athena**: A persistent, context-aware AI assistant capable of streaming intelligent explanations based entirely on validated telemetry.

---

## System Architecture

Athena enforces a strict, unidirectional data flow and clear separation of concerns across its architectural layers.

```text
Raw Event Data
      ↓
  Warehouse (DuckDB / SQL Views)
      ↓
Football Intelligence Engine (Capability Engineering)
      ↓
Collective Intelligence Engine (Team Aggregation)
      ↓
Reasoning Layer (Decision & Recruitment Engines)
      ↓
Evidence Packets (Explanation Engine)
      ↓
 LLM Narration
      ↓
   Frontend (Streamlit / Service Layer)
```

**Layer Responsibilities:**
1. **Warehouse**: Handles raw data persistence, indexing, and SQL aggregation.
2. **Intelligence Engines (FIE/CIE)**: Processes statistical aggregates into normalized [0-100] capabilities, archetypes, and tactical identities.
3. **Reasoning Layer**: Synthesizes capabilities into actionable decisions, gap analyses, and recruitment recommendations.
4. **Explanation Engine**: Constructs deterministic prompts and `EvidencePackets` for safe LLM consumption.
5. **Frontend**: A thin presentation layer that coordinates via stable service modules, strictly isolated from backend implementation details.

---

## Intelligence Pipeline

1. **Ingestion**: Raw JSON event data is parsed into Parquet format.
2. **Aggregation**: DuckDB processes the Parquet files into analytical SQL views (Match, Player, and Team summaries).
3. **Feature Engineering**: Summary views are translated into `PlayerFeatureVector` objects.
4. **Capability Generation**: Vectors are scored mathematically to produce a `CapabilityProfile` encompassing traits like Ball Progression, Press Resistance, and Attacking Threat.
5. **Reasoning Synthesis**: Capabilities are evaluated against positional cohorts to produce `DecisionCards` containing percentile-backed explanations.
6. **User Delivery**: The UI consumes the final Canonical Schemas (`PlayerProfile`, `PlayerDecisionCard`) via the Frontend Service Layer.

---

## Key Concepts

- **Capabilities**: Standardized [0-100] metrics derived from raw statistical features (e.g., *Chance Creation*, *Ball Security*).
- **Archetypes**: A classification of a player's primary role (e.g., *Deep Lying Playmaker*, *Target Man*) derived from capability clustering.
- **Collective Intelligence**: The emergent tactical profile of a team based on the aggregate capabilities of its squad.
- **Decision Cards**: The final synthesized evaluation of a player or team, highlighting top strengths, bottom weaknesses, and cohort percentiles.
- **Counterfactual Analysis**: The ability to project changes in team output by swapping players in and out of the squad context.
- **Recruitment Intelligence**: Ranking players not by simple stats, but by their mathematical compatibility with a desired capability profile.
- **Replaceability**: Measuring how dependent a team is on a single player for a specific capability (e.g., identifying a critical single point of failure in ball progression).
- **Tactical Identity**: The dominant playing style of a team (e.g., *Possession-Dominant*, *Counter-Attacking*).

---

## Current Dataset

Out of the box, Athena integrates with the **StatsBomb Open Data** catalogue. 
- **Coverage**: Competitions spanning multiple decades including the World Cup, Euros, Champions League, La Liga, and FA WSL.
- **Seasons**: Extensive historical data containing thousands of matches and tens of thousands of unique player profiles.

---

## Dataset Limitations

While the open dataset provides an excellent foundation, users should be aware of the following limitations in the public tier:
- **Incomplete Competition Coverage**: Not all weeks of a league or all teams are universally covered.
- **Missing Recent Seasons**: The most current active seasons are often excluded from the free tier.
- **No Optical Tracking**: Lacks skeletal and broadcast tracking data.
- **Missing Off-Ball Events**: Primarily focuses on on-ball event data, limiting insights into off-ball movement and spatial occupation.
- **Limited Transition Metrics**: Precise transition states and pressing triggers are sometimes difficult to infer purely from event data.
- **Incomplete Pass Networks**: Missing continuous 22-man coordinate data limits absolute pass network fidelity.

---

## Bring Your Own Data

Athena is explicitly **dataset-agnostic**. 

While it ships with a StatsBomb adapter, the Intelligence Architecture is entirely decoupled from the ingestion source. The warehouse pipeline is designed to ingest data from any modern event or tracking provider, including:
- **Opta**
- **Wyscout**
- **StatsBomb 360**
- **SkillCorner**
- **Second Spectrum**
- **Internal club proprietary datasets**

Replacing the data source **does not require redesigning the intelligence architecture**. By writing a simple adapter to map your provider's raw XML/JSON/CSV into Athena's `PlayerRaw` and `MatchRaw` schemas, the entire Football Intelligence Engine, Recruitment Engine, and LLM Explainability layer will function automatically without modification.

---

## Repository Structure

```text
athena/
├── backend/
│   ├── collective/      # Team intelligence & tactical identity
│   ├── explanation/     # LLM orchestration, prompts & intents
│   ├── intelligence/    # Player profiling, archetypes & decision cards
│   └── recommendation/  # Recruitment & counterfactual logic
├── data/
│   ├── raw/             # Raw JSON event data
│   └── warehouse/       # Processed Parquet & DuckDB indices
├── frontend/
│   ├── components/      # UI widgets (Ask Athena, Selectors)
│   ├── data/            # Frontend Service Layer (API Facade)
│   ├── workspaces/      # Dashboard, Player, Team, Recruitment Views
│   └── app.py           # Streamlit entry point
├── scripts/             # Data bootstrapping & ETL pipelines
├── shared/              # Canonical Schemas & configuration
└── tests/               # Unit, Integration & Regression suites
```

---

## Design Principles

- **Evidence Before AI**: The LLM narrates; it never calculates.
- **Deterministic Reasoning**: All insights must be traceable back to mathematical percentiles and raw features.
- **Single Source of Truth**: Unified canonical schemas (`PlayerProfile`, `CollectiveProfile`) are used universally.
- **Separation of Concerns**: The Frontend Service layer isolates the UI from Backend Engines and Warehouse internals.
- **Stable Public APIs**: Consumer layers only interact with public contracts (`PlayerDecisionCard`, `CapabilityExplanation`).

---

## Future Roadmap

- **Optical Tracking Integration**: Expanding the ETL layer to ingest spatial and tracking broadcast data for off-ball analysis.
- **Advanced Counterfactuals**: Implementing dynamic squad-building workspaces for real-time scenario simulation.
- **Expanded Tactical Identities**: Enhancing Collective Intelligence to support more granular phase-of-play styles (e.g., High-Block Pressing vs Mid-Block Rest Defense).
- **Dynamic Cohort Filtering**: Allowing users to filter percentile calculations by specific leagues, age brackets, or timeframes on the fly.
