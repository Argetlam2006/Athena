# Retrieval v1.0 — Architecture Freeze

**Date**: 2026-07-24
**Status**: Frozen — controlled rollout in progress

## Scope

Retrieval v1.0 comprises:

- **13 Python source files** across 4 packages (`backend/knowledge/`, `backend/reasoning/`, `backend/retrieval/`, `shared/schemas/`)
- **4 strategies**: ComparisonStrategy, PlayerAnalysisStrategy, ReplacementStrategy, GeneralStrategy
- **3 claim types**: `capability`, `archetype`, `role_fit`
- **21 edge types** (declared in registry, 5 built in graph)
- **10,242 entities**, **108,349 edges** in the entity graph
- **6 qualifier kinds** with 3 severity levels
- **30-question benchmark suite** + 25 stress tests + CI quality gate
- **3,281 lines** of retrieval-specific code (including schemas, tests, and documentation)

## Freeze Policy

No architectural redesign. The following are frozen:

1. **Entity Graph** — node/edge schema, query interface, builder pipeline, edge registry pattern
2. **Claim Schema** — `Claim` dataclass, `ClaimType` enum, `ClaimQualifier` / `ClaimProvenance` contracts
3. **Retrieval Plan** — `RetrievalPlan` / `RetrievalStep` IR, step types, serialisation contract
4. **Evidence Bundle** — `EvidenceBundle`, `Coverage`, `CoverageValidator` contracts
5. **Strategy Dispatch** — registry pattern, `supports()/plan()` contract, singleton caching
6. **Execution** — `CLAIM_DISPATCH` registry, `RetrievalExecutor` contract
7. **Qualifier Derivation** — registry pattern, derivation from engine outputs only
8. **Bridge + Shadow** — integration path, tracing metadata fields, shadow deployment harness

## What May Change (extension only)

New capabilities must be implemented through existing registries:

| Extension Point | What You Can Add |
|---|---|
| `ClaimType` enum | New claim types |
| `CLAIM_DISPATCH` | New projector functions |
| `_strategy_registry` | New strategy classes |
| `EDGE_REGISTRY` | New edge type declarations (with builder projection) |
| `QUALIFIER_RULES` | New qualifier kinds (with derivation logic) |
| Benchmarks | New questions, categories, thresholds |

## Rollout Decision

**Recommendation**: Enable retrieval as the default Ask Athena pipeline for comparison, player analysis, and recruitment queries. The infrastructure is stable, benchmarked, and hardened.

**Rollback path**: Set `ATHENA_USE_RETRIEVAL=false` (the default) to restore the previous pipeline. All original code paths remain intact.

**Current deployment state**: Shadow mode (`ATHENA_DEPLOYMENT_MODE=shadow`). Retrieval runs for every request and logs metrics. The existing response is still returned to users.

**Gate metrics for full enablement** (after shadow data collection):
- <5% coverage failure rate
- <2% unexpected error rate
- P95 latency under 3,000ms for comparison queries
- All benchmark thresholds passing in CI

## Known Gaps (not blocking freeze)

1. **Single-graph-node entity ID assumption** — competition and career profiles share `player_id`. If the store ever assigns composite IDs, the entity model breaks silently. Documented in review.
2. **Temporal context loss in triggers edges** — player-same-signal across seasons is deduplicated. Acceptable for the current retrieval use case.
3. **No cycle detection in multi-hop traversal** — documented limitation; safe for the current acyclic graph.
4. **Cross-cohort filtering not supported** — structured queries by competition+position require a new strategy or an extended intent model.

## Verification

The freeze is verified by:

- `scripts/run_retrieval_ci.py` — runs stress tests + benchmark + threshold checks
- `tests/evaluation/retrieval_stress.py` — 25 architectural invariant tests
- `tests/evaluation/retrieval_expanded_benchmark.py` — 30-question benchmark with per-question metrics
