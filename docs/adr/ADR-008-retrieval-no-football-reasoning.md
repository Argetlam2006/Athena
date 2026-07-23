# ADR-008 — Retrieval Performs No Football Reasoning

**Date**: 2026-07-24
**Status**: Accepted

## Context

The retrieval layer sits between Athena's deterministic football intelligence and the LLM. It has access to entity graphs, edge relationships, and capability scores — all of which are football knowledge. The risk was that retrieval logic would absorb football heuristics (e.g., "only consider players with more than 10 matches," "prioritize progression over security in possession systems"), creating a second source of football truth that could diverge from the deterministic engine.

## Decision

The retrieval layer performs **no football reasoning**. It is an extraction and projection layer with three responsibilities:

1. **Extraction**: traverse typed edges to find entities and relationships the engine already defined
2. **Projection**: convert engine-output data structures into entity-attached Claims
3. **Validation**: verify that required claim types are present before prompt building

Football thresholds, confidence rules, qualifier logic, and relationship weights are all **inherited from the deterministic engine** — they live in `backend/intelligence/`, `backend/recommendation/`, `shared/constants.py`, and `shared/schemas.py`, not in the retrieval layer.

## Mechanically Enforced

The edge registry (`backend/knowledge/registry.py`) requires every edge type to declare its source engine and source function. Any edge type that cannot point to a function in the FIE, DecisionEngine, or CollectiveEngine is rejected at build time.

The `CLAIM_DISPATCH` registry maps claim types to projection functions. Projectors read from the store and the graph, but never apply football thresholds.

The executor (`backend/retrieval/execution.py`) is plan-agnostic — it executes steps without interpreting their football meaning.

## Consequences

- ✓ The engine remains the single source of football truth
- ✓ An edge type that doesn't come from the engine cannot exist in the graph — the invariant is mechanically checkable
- ✓ Adding a new football relationship means adding it to the engine first, then registering its edge type
- ⚠ The retrieval layer sometimes needs access to engine thresholds (e.g., qualifier derivation reads `matches_played` thresholds). These are imported from `shared/constants.py`, never duplicated — a discipline enforced by code review
