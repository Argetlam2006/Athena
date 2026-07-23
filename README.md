# Athena

Athena is an evidence-grounded, neuro-symbolic football intelligence platform. It combines deterministic football analytics with structured knowledge retrieval and LLM reasoning over verified evidence — producing explainable, auditable football decisions rather than black-box predictions or raw dashboards.

---

## What is Athena?

Athena transforms raw match event data into football intelligence through a layered architecture:

- **Deterministic analytics** — mathematical capability models compute every player and team score from real event data. Given the same inputs, Athena always produces the same outputs.
- **Explainable AI** — every score traces back through capabilities to specific metrics and raw events. Nothing is hidden inside a latent representation.
- **Evidence-grounded reasoning** — the LLM receives pre-verified, structured evidence. It communicates football analysis; it never computes it.
- **Structured knowledge retrieval** — a typed entity graph and deterministic retrieval planner extract relevant evidence for any football question, replacing ad-hoc context assembly.

---

## Why Athena?

Traditional football analytics tools share common limitations that Athena directly addresses:

- **Dashboards overload** — grids of raw statistics require domain expertise to interpret and offer no structured reasoning or conclusions.
- **Black-box ML** — predictive models produce scores without explainable traceability. A scout cannot verify why a player received a certain rating.
- **Vanilla LLMs** — large language models without structured context hallucinate statistics, invent comparisons, and provide no audit trail.
- **Document-based RAG** — retrieving chunks of prose documents loses the structured relationships between players, teams, capabilities, and tactical contexts that football analysis depends on.

Athena's philosophy, **"Evidence Before AI,"** rejects all four approaches. The deterministic engine performs the football intelligence. The retrieval layer selects relevant evidence from a structured knowledge graph. The LLM communicates the evidence. At no point does the model invent, predict, or compute football analysis from first principles.

---

## Core Philosophy

- **LLMs never calculate football intelligence.** Every capability score, percentile rank, and decision signal is produced by explicit mathematical formulas applied to real event data.
- **Deterministic football models produce structured evidence.** The Football Intelligence Engine, Collective Intelligence Engine, and Decision Intelligence Engine each produce typed, traceable artifacts with full provenance.
- **Retrieval selects relevant evidence.** A typed entity graph and deterministic retrieval planner identify which evidence is needed to answer a question, then traverse graph relationships to collect it.
- **The LLM communicates the evidence.** The model receives pre-validated claims with provenance and qualifiers. It can narrate, compare, and reason over evidence — but never invent it.

---

## Architecture Overview

```
Football Data (StatsBomb)
      |
DuckDB Warehouse (SQL Views)
      |
Football Intelligence Models (FIE / CIE / Decision Engine)
      |
Entity Knowledge Graph (nodes + typed edges)
      |
Retrieval Strategy + Plan (deterministic, per-intent)
      |
Claim Projection (entity-attached assertions)
      |
Coverage Validation (evidence sufficiency check)
      |
Evidence Bundle -> PromptBuilder -> LLM
      |
Evidence Inspector (visible to users)
```

The pipeline is unidirectional. Each layer consumes typed contracts from the layer above and produces typed contracts for the layer below. No layer bypasses another.

---

## Key Components

### Football Intelligence Models

Three deterministic engines produce all football knowledge:

- **Football Intelligence Engine (FIE)** — computes 6 core capabilities (Ball Progression, Chance Creation, Ball Security, Press Resistance, Defensive Activity, Attacking Threat) from per-90 metrics, produces position-relative percentile scores (0-100), assigns rule-based archetypes, and generates decision signals.
- **Collective Intelligence Engine (CIE)** — aggregates player capabilities into team-level profiles, computes tactical identities, structural bottlenecks, capability concentration (HHI), and system fragility (replaceability index per player).
- **Decision Intelligence Engine** — produces player comparisons (Euclidean similarity in capability space), recruitment rankings (weighted fit scoring against criteria), tactical fit evaluation (decomposed compatibility context), and counterfactual analysis (capability delta when adding or removing players).

### Knowledge Graph

The Entity Graph is a DuckDB-indexed projection of all engine outputs. It contains:

- **10,242 entities** — players (9,884) and teams (358), each with typed metadata
- **108,349 edges** across 21 registered relationship types, 5 currently built
- **Edge types include**: `has_capability`, `member_of`, `classified_as`, `fragile_on`, `has_squad_capability`, `similar_to`, `replacement_for`, `fits_style`, `bottlenecks_into`, and 12 more

Every edge is deterministic and declared in a central registry with its source engine and function. The graph is rebuilt idempotently from the Intelligence Store; identical store state always produces identical graph state.

### Claim Layer

Claims are the only reasoning artifact the LLM ever receives. Each Claim is:

- **Entity-attached** — asserts something about a specific player, team, or relationship
- **Deterministic** — produced by projecting engine outputs, never by LLM inference
- **Provenanced** — carries engine name, version lineage, store fingerprint, and rule references
- **Qualified** — pre-computed caveats for sample size, league context, regression risk, data coverage, and role dependence

Claims are produced through registered projectors and dispatched via a typed registry (`CLAIM_DISPATCH`). Adding a new claim type means adding a `ClaimType` enum member, a projector function, and a registry entry.

### Retrieval Strategies

Strategies map intents to plans. Each strategy declares which intent types it supports and what retrieval steps are needed.

Five strategies are registered:

| Strategy | Intent | Claim Types Produced |
|---|---|---|
| **ComparisonStrategy** | compare_players | capability, archetype (14 claims) |
| **PlayerAnalysisStrategy** | player_analysis | capability, archetype (7 claims) |
| **ReplacementStrategy** | recruitment | capability, archetype, role_fit (12 claims) |
| **TeamAnalysisStrategy** | team_analysis | team_capability, team_fragility (11 claims) |
| **GeneralStrategy** | (fallback) | none — existing LLM knowledge used |

Strategies are registered via `@register_strategy` decorator. The dispatcher selects the highest match score. No dispatch chain modification needed for new strategies.

### Coverage Validation

Before any prompt reaches the LLM, a `CoverageValidator` checks that the EvidenceBundle contains all claim types the strategy requires. If critical evidence is missing, the pipeline raises `CoverageValidationError` and the prompt is never built. This is the mechanically-enforced version of "Evidence Before AI."

### Evidence Bundle

The `EvidenceBundle` is the validated handoff between retrieval and generation. It carries claims, coverage metadata (which claim types were sought vs. satisfied), store fingerprint for staleness detection, and the original intent for audit.

### Evidence Inspector

Every retrieval-assisted response includes a collapsible Evidence Inspector panel. Users can inspect:

- Retrieval strategy used
- Claim types produced
- Coverage result (which types were satisfied vs. missing)
- Retrieval latency
- Provenance (engine, version, plan ID)
- Execution trace (entities, traversals, prompt size)

The Evidence Inspector makes the "Evidence Before AI" philosophy visible to users rather than remaining an internal architectural concept.

### Decision Intelligence

The Decision Intelligence Engine provides:

- **Player comparison** — quantitative comparison across all 6 capabilities with Euclidean similarity scoring
- **Recruitment ranking** — weighted fit scoring against position, tactical style, and required capability criteria
- **Tactical fit evaluation** — decomposed compatibility scores (capability alignment, identity preservation, dependency relief, availability impact)
- **Replacement analysis** — capability restoration scoring against the focal player's profile
- **Counterfactual analysis** — capability delta when adding or removing players from a squad

---

## Retrieval Architecture (v1)

Retrieval v1 is the stable retrieval infrastructure that connects deterministic intelligence to LLM reasoning. It is built around:

- **Typed knowledge graph** — entities (player, team, capability, etc.) connected by typed, registered edges with known provenance
- **Deterministic traversal** — the executor follows plan steps exactly, with no heuristics or ranking
- **Structured claims** — entity-attached assertions with score, confidence, qualifiers, and traceability chain
- **Retrieval planning** — strategies produce a `RetrievalPlan` IR that separates what to retrieve from how to execute it
- **Coverage validation** — rejects insufficient evidence before the prompt is built
- **Registry-based extension** — strategies, claim types, edge types, and qualifiers each have their own registry; adding new capabilities never requires modifying dispatch code
- **Evidence bundles** — the validated handoff between retrieval and generation

The retrieval architecture is frozen at v1.0. Future extensions should use the existing registries (strategy, claim type, edge, qualifier) without modifying the architectural contracts.

---

## Core Capabilities

- **Player Analysis** — capability profiles (6), archetype classification, decision signals, strengths and weaknesses, similarity search
- **Team Analysis** — squad-average capability profiles, structural fragility (replaceability), tactical identity classification
- **Player Comparison** — quantitative cross-player comparison across all 6 capabilities, shared strengths, key differences
- **Recruitment Intelligence** — deterministic fit scoring, position-targeted search, tactical style matching, replacement recommendation
- **Counterfactual Analysis** — capability delta when adding or removing players from a squad context
- **Ask Athena** — context-aware natural language assistant powered by the retrieval pipeline, with Evidence Inspector for every response
- **Evidence Inspector** — visible retrieval trace for every analytical answer

---

## Repository Structure

```
athena/
  backend/
    collective/         Team intelligence, fragility, bottlenecks, identity
    etl/                StatsBomb data normalization pipeline
    explanation/        Prompt builder, conversation manager, intent classifier
    intelligence/       Player profiling, capability scoring, archetypes, signals
    knowledge/          Entity graph builder, query interface, edge registry
    reasoning/          Claim projectors, qualifier derivation
    recommendation/     Comparisons, recruitment, tactical fit evaluation
    retrieval/          Strategies, execution, bridge, coverage validation, shadow
    warehouse/          DuckDB connection, analytical SQL queries
  data/
    raw/                Raw StatsBomb event data
    warehouse/          Processed Parquet, DuckDB indices, intelligence store
  frontend/
    components/         Ask Athena drawer, Evidence Inspector
    data/               Frontend service layer, retrieval service
    workspaces/         Dashboard, Player, Team, Recruitment views
    app.py              Streamlit entry point
  scripts/              Data bootstrapping, ETL, maintenance
  shared/
    config/             Capability definitions, signals, role mappings
    schemas/            Canonical data contracts, retrieval schema
  tests/                Unit, integration, regression, evaluation suites
  docs/
    adr/                Architecture Decision Records
```

---

## Design Principles

- **Evidence Before AI** — the LLM narrates structured evidence; it never calculates football intelligence
- **Deterministic Football Intelligence** — every capability score is produced by an explicit formula applied to real event data; same inputs always produce the same outputs
- **Explainability by Design** — every score traces back through capabilities to specific metrics and raw event definitions
- **Neuro-Symbolic Architecture** — deterministic models produce structured knowledge; machine learning (LLM) reasons over it as a communication layer
- **Registry-Based Extensibility** — strategies, claim types, edge types, and qualifiers are each registered in a central dispatch table; adding new capabilities never requires modifying dispatch code
- **Stable Contracts** — the retrieval-to-generation boundary is defined by `Claim` and `EvidenceBundle`; the prompt builder and provider interface never touch retrieval internals
- **Single Source of Truth** — canonical schemas (PlayerProfile, CollectiveProfile) are used universally; the entity graph is a deterministic projection, never a parallel source
- **Retrieval is Deterministic** — same query plus same graph always produces the same evidence bundle
- **LLMs Communicate, Never Calculate** — the model may narrate, compare, and reason over evidence but never invent, predict, or compute football analysis

---

## Current Dataset

Athena ships with **StatsBomb Open Data**:

- **Competitions**: World Cup, UEFA Euro, Champions League, Premier League, La Liga, FA WSL, NWSL, and more
- **Seasons**: Multiple decades of match data across all covered competitions
- **Scale**: Thousands of matches, tens of thousands of player profiles across 3 granularity levels (competition, season, career)
- **Entity Graph**: 10,242 entities (9,884 players, 358 teams), 108,349 edges across 5 built relationship types

---

## Quick Start

```
# Clone and install
git clone https://github.com/Argetlam2006/Athena.git
cd Athena
pip install -r requirements.txt

# Bootstrap the data pipeline (downloads StatsBomb data, runs ETL, builds warehouse and intelligence store)
python scripts/maintenance/bootstrap.py

# Launch Athena
streamlit run frontend/app.py

# Run the test suite
pytest
```

---

## Development Status

**Retrieval v1 is stable infrastructure.** It is frozen at v1.0 and available through:

- Feature flag: `ATHENA_USE_RETRIEVAL=true` (env var)
- Shadow deployment: runs in parallel with existing pipeline, logs metrics, returns existing response
- CI quality gate: `scripts/run_retrieval_ci.py`

Future development focuses on expanding football intelligence models through existing extension points — adding new strategies, claim types, edge types, and qualifiers through the registries — without modifying the retrieval architecture.

---

## Roadmap

- **Tactical intelligence** — richer playing-style models, phase-of-play analysis, tactical pattern recognition
- **Team bottlenecks** — upstream-to-downstream capability gaps, structural dependency mapping
- **Cross-team comparison** — comparative squad analysis, opponent preparation workflows
- **Squad planning** — multi-player roster construction, depth analysis, positional coverage
- **Recruitment intelligence** — richer role-fit reasoning, scouting report generation, long-term replacement planning
- **Decision workflows** — composed multi-strategy analysis (replacement planning, squad audit, tactical fit assessment)

---

## Dataset Limitations

Athena is dataset-agnostic but ships with StatsBomb Open Data, which has known limitations:

- Incomplete competition coverage across all weeks and teams
- Missing recent seasons in the public tier
- No optical tracking or broadcast tracking data
- Limited off-ball event data
- Incomplete transition state and pressing trigger information

The intelligence architecture is fully decoupled from the data source. Custom adapters can map any provider's format (Opta, Wyscout, StatsBomb 360, SkillCorner, Second Spectrum, internal club data) into Athena's `PlayerRaw` and `MatchRaw` schemas, making the entire intelligence pipeline function without modification.
