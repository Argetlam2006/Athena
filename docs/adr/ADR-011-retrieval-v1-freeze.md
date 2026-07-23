# ADR-011 — Retrieval v1 Freeze

**Date**: 2026-07-24
**Status**: Accepted

## Context

Retrieval v1.0 was built incrementally across six milestones (M0–M5), hardened, integrated into the production Ask Athena pipeline, expanded with new strategies and claim types, and validated against a 30-question benchmark and 25 stress tests. The architecture reached feature-completeness. The question was: when should we stop making architectural changes and shift to product-focused development?

## Decision

Retrieval v1.0 is frozen as of 2026-07-24. No architectural changes are permitted without strong evidence that an existing invariant prevents a meaningful product capability.

The following are frozen:
- Entity Graph schema and query interface
- Claim dataclass, ClaimType enum, and provenance contracts
- RetrievalPlan/RetrievalStep IR contract
- EvidenceBundle and Coverage schemas
- Strategy registry and dispatch contract
- CLAIM_DISPATCH registry pattern
- Executor contract (plan-agnostic traversal + projection)
- Qualifier derivation contract
- Bridge integration and tracing
- Shadow deployment harness

The following extension points remain open:
- New strategy classes (via @register_strategy)
- New ClaimType enum members + projector functions (via CLAIM_DISPATCH)
- New EdgeType members + builder methods (via EDGE_REGISTRY)
- New QualifierKind members + derivation logic (via QUALIFIER_RULES)
- New benchmark questions and CI thresholds

## Rationale

- **Stability enables product focus**: freezing the infrastructure lets engineers build football intelligence without worrying about the retrieval layer shifting underneath them.
- **Extension points are sufficient**: the four registries cover every reasonable addition the current product roadmap requires (team analysis, squad analysis, tactical retrieval, richer role-fit reasoning).
- **Architectural changes are expensive**: every ADR in this directory required design discussions, implementation, and validation. A v2.0 redesign should only be considered when a concrete product requirement cannot be met through the existing extension points.

## Consequences

- ✓ Future Athena improvements focus on football intelligence, not retrieval infrastructure
- ✓ Contributors rarely need to modify the retrieval layer
- ✓ Retrieval v1 is documented, benchmarked, and frozen — it will not change incompatibly
- ⚠ If a product requirement genuinely cannot be met through existing extension points, we must revisit the freeze. This is acceptable — the freeze is a policy, not a contract.

## References

- [RETRIEVAL_V1_FREEZE.md](../../RETRIEVAL_V1_FREEZE.md) — detailed freeze scope and file inventory
- [docs/RETRIEVAL_CAPABILITY_MATRIX.md](../../docs/RETRIEVAL_CAPABILITY_MATRIX.md) — current strategies, claim types, and edge types
