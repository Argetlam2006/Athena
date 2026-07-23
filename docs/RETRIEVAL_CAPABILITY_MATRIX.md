# Athena Retrieval — Strategy Capability Matrix

## Architecture

The retrieval layer comprises three layers:

- **Entity Graph** — typed deterministic knowledge index built from the Intelligence Store
- **Retrieval** — strategy dispatch, plan generation, and execution against the graph
- **Reasoning** — Claims (atomic assertions) and EvidenceBundles (validated handoff)

## Current Strategies

| Strategy | Intent Type(s) | Entities Required | Claim Types Produced | Claim Count | Status |
|---|---|---|---|---|---|
| **ComparisonStrategy** | `COMPARE_PLAYERS` | `focus_player`, `compare_player` | `capability` (x2), `archetype` (x2) | 14 (7 per player) | **Production-ready** |
| **PlayerAnalysisStrategy** | `PLAYER_ANALYSIS` | `focus_player` | `capability` (6), `archetype` (1) | 7 | **Production-ready** |
| **ReplacementStrategy** | `RECRUITMENT` (plus keyword "replacement") | `focus_player` | `capability` (6), `archetype` (1), `role_fit` (5) | 12 | **Production-ready** (role_fit has coverage gaps when team context unavailable) |
| **GeneralStrategy** | Any unmatched intent | (none) | (none) | 0 | **Fallback** — returns empty bundle, passes through to existing LLM knowledge |

## Claim Types

| Claim Type | Projector | Produced By | First-Class Qualifiers | Supports (traceability) |
|---|---|---|---|---|
| `capability` | `capability_claims()` | Comparison, PlayerAnalysis, Replacement | Yes (sample_size, league_context, regression_risk, data_coverage, overperformance_caveat) | Yes — 2–6 `SupportingMetric` entries per capability |
| `archetype` | `archetype_claim()` | Comparison, PlayerAnalysis, Replacement | Yes | Yes — contributing capabilities |
| `role_fit` | `role_fit_claims()` | Replacement | Yes | Yes — decomposed fit dimensions (alignment, identity, relief, availability) |

## Qualifiers

| Qualifier Kind | Severity Levels | Source | Applies To |
|---|---|---|---|
| `sample_size` | informational / cautionary / material | matches_played thresholds | All claim types |
| `league_context` | informational | competition field | All claim types |
| `data_coverage` | cautionary / material | minutes_played threshold | All claim types |
| `regression_risk` | cautionary | goals_minus_xg on small volume | `capability` (attacking_threat) |
| `overperformance_caveat` | informational | goals_minus_xg > 2.0 | `capability` (attacking_threat) |
| `role_dependence` | informational | position_gated signals | `capability` (when position-dependent) |

## Edge Types (Entity Graph)

| Edge Type | Origin | Engine | Produced By | Status |
|---|---|---|---|---|
| `HAS_CAPABILITY` | Direct | FIE | GraphBuilder | **Built** |
| `MEMBER_OF` | Direct | FIE | GraphBuilder | **Built** |
| `CLASSIFIED_AS` | Direct | FIE | GraphBuilder | **Built** |
| `HAS_SQUAD_CAPABILITY` | Direct | Collective | GraphBuilder | **Built** |
| `FRAGILE_ON` | Direct | Collective | GraphBuilder | **Built** |
| `TRIGGERS` | Direct | DecisionEngine | GraphBuilder | **Built** (edges present only when signals exist in store) |
| `HAS_BOTTLENECK` | Direct | Collective | Not yet built | **Registered** (schema + registry exist) |
| `HAS_CONCENTRATION` | Direct | Collective | Not yet built | **Registered** (schema + registry exist) |
| `SIMILAR_TO` | Derived | DecisionEngine | Not yet built | **Registered** (uses euclidean_distance) |
| `REPLACEMENT_FOR` | Derived | DecisionEngine | Not yet built | **Registered** (uses recommend_replacement) |
| `FITS_STYLE` | Derived | DecisionEngine | Not yet built | **Registered** (uses evaluate_tactical_fit) |
| `BOTTLENECKS_INTO` | Direct | Collective | Not yet built | Registered |
| `SEASON_OF` / `CAREER_OF` / `SUPERSEDES` | Direct | FIE | Not yet built | Registered |
| `SHARED_STRENGTH` / `KEY_DIFFERENCE` | Direct | DecisionEngine | On-demand | Registered (via compare_players) |
| `POSTED_METRIC` | Direct | FIE | Not yet built | Registered |
| `REQUIRES` / `VALUES` | Derived / Direct | DecisionEngine / FIE | Not yet built | Registered |
| `DEPENDS_ON` | Derived | Collective | Not yet built | Registered |

## Future Strategies (planned)

| Strategy | Intent | New Claim Types | Requires | Priority |
|---|---|---|---|---|
| **TeamAnalysisStrategy** | `TEAM_ANALYSIS` | `team_capability` (team-level), `team_fragility`, `team_bottleneck` | Build `HAS_BOTTLENECK` + `HAS_CONCENTRATION` edges; add 3 `ClaimType` + 3 projector methods | **High** — covers team intelligence gap |
| **CounterfactualStrategy** | `COUNTERFACTUAL` | `counterfactual_delta` | Build `DEPENDS_ON` edges; new projector; cross-player edge traversal | **Medium** — dependent on fragility edge maturity |
| **SquadDiagnosisStrategy** | `SQUAD_DIAGNOSIS` | `fragility`, `concentration`, `dependency` | Same as TeamAnalysis + team→player multihop | **Medium** |

## Strategy Dispatch Logic

The dispatcher iterates registered strategies in registry order and selects the one with the highest `supports()` score. Current scores:

| Strategy → Intent | comparison | player_analysis | recruitment | counterfactual | squad_diagnosis | general |
|---|---|---|---|---|---|---|
| **ComparisonStrategy** | **1.0** | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| **PlayerAnalysisStrategy** | 0.0 | **1.0** | 0.0 | 0.0 | 0.0 | 0.0 (0.6 on keyword match) |
| **ReplacementStrategy** | 0.0 | 0.0 | **0.8** | 0.0 | 0.0 | 0.0 (0.9 on keyword "replacement") |
| **GeneralStrategy** | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 | **0.5** |

## Coverage Validator Rules

Required claim types per intent (from plan metadata, not validator):

| Intent | Required | Optional |
|---|---|---|
| `COMPARE_PLAYERS` | `capability` | `archetype`, `shared_strength`, `key_difference` |
| `PLAYER_ANALYSIS` | `capability`, `archetype` | (none) |
| `RECRUITMENT` | `capability`, `archetype` | `role_fit` |
| All others | (none) | (none) |

## Performance Baselines (current)

| Strategy | Avg Retrieval Time | Max Retrieval Time | Avg Prompt Size | Avg Claims |
|---|---|---|---|---|
| ComparisonStrategy | ~1,050ms | ~1,360ms | ~30,300B | 14 |
| PlayerAnalysisStrategy | ~550ms | ~680ms | ~15,400B | 7 |
| ReplacementStrategy | ~775ms | ~890ms | ~25,300B | 12 |
| GeneralStrategy (fallback) | ~0.3ms | ~1ms | ~400B | 0 |

## Related Documentation

- [Retrieval Architecture Contracts](../../shared/schemas/retrieval.py) — schema definitions
- [Edge Registry](../../backend/knowledge/registry.py) — edge type declarations
- [Qualifier Rules](../../backend/reasoning/qualifiers.py) — qualifier derivation
- [Benchmark Suite](../../tests/evaluation/retrieval_expanded_benchmark.py) — regression tests
- [CI Gate](../../scripts/run_retrieval_ci.py) — automated quality checks
