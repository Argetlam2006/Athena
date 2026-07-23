# ADR-007 — Claims as the Retrieval Boundary

**Date**: 2026-07-24
**Status**: Accepted

## Context

The retrieval architecture needed a reasoning artifact that could be produced deterministically and consumed by the LLM without modification. The existing codebase had `EvidencePacket` (a flat list of metrics), `PlayerProfile` (a complete player intelligence package), and `ScoutingReport` (an LLM-generated report). None served as a suitable boundary: `EvidencePacket` carried no provenance, `PlayerProfile` mixed domain data with reasoning, and `ScoutingReport` was an LLM output that couldn't flow into another LLM.

## Decision

The `Claim` is the only reasoning artifact consumed by the LLM. Claims:

- Are **deterministic projections** of engine outputs — they never introduce new football knowledge
- Carry **full provenance** (engine, version lineage, store fingerprint, rule references)
- Include **first-class qualifiers** derived from engine confidence bands and thresholds
- Have a **deterministic claim_id** = hash(about_entity, predicate_key, store_fingerprint)
- Are **entity-attached** (they assert something about an EntityRef)

The `EvidenceBundle` is the validated collection of claims that serves as the handoff between retrieval and generation. It is transient — assembled per question, never stored permanently.

## Rationale

- **Single interface**: the prompt builder, system prompt, coverage validator, and provider integration all depend on one artifact type. Every downstream component knows what to expect.
- **Provenance is non-negotiable**: every claim carries enough metadata to trace back through capabilities → metrics → events (FOOTBALL_INTELLIGENCE_ENGINE.md §9.1). This makes the retrieval audit trail complete.
- **Qualifiers before the LLM**: caveats about sample size, regression risk, league context, and data quality are pre-computed and attached to claims. The LLM receives them as part of the assertion, not as a separate instruction to "be careful about small samples."

## Alternatives Considered

1. **Raw engine outputs as context**: pass `CapabilityProfile` or `PlayerProfile` directly to the LLM. Rejected because these mix domain data (what a player is) with reasoning data (how they compare) and carry no provenance.
2. **Entity-attached graphs as context**: pass the entity graph subgraph to the LLM. Rejected because this would require the LLM to interpret graph edges and node metadata — exactly the football reasoning the architecture is designed to keep deterministic.
3. **Unified Claim+Bundle**: merge Claim and EvidenceBundle into one type. Rejected because Claims change when the assertion schema evolves, while Bundles change when the handoff contract evolves — they change at different rates.

## Consequences

- ✓ All downstream consumers (prompt builder, validator, telemetry) depend on exactly two types
- ✓ Adding a new claim type requires adding a `ClaimType` enum member, a projector method, and a dispatch entry — no downstream changes
- ✓ The `claim_id` hash enables deterministic deduplication and caching
- ⚠ The claim schema is frozen at v1.0.0 — changing it requires a version bump and migration
