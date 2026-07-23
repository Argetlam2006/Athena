# ADR-006 — Evidence Before AI in the Retrieval Layer

**Date**: 2026-07-24
**Status**: Accepted (supersedes ADR-001–005 as cross-cutting design principle)

## Context

Athena's core philosophy is "Evidence Before AI": the deterministic engine performs football intelligence, and the LLM communicates the results. The retrieval layer extends this principle from a policy to an architecture.

The fundamental question was: should the LLM be able to retrieve evidence on demand (tool-use, function-calling), or should retrieval be deterministic and complete before the prompt is built?

## Decision

Retrieval is **deterministic retrieve-then-generate**. The LLM never retrieves evidence. Athena selects, validates, and ranks evidence before the prompt is built. The LLM only reasons over Claims contained within an EvidenceBundle — never touching the graph, edge tables, or raw feature vectors.

## Rationale

- **Auditability**: every retrieval decision is logged in the RetrievalPlan and visible in the EvidenceBundle's coverage metadata. A deterministic plan replay produces identical results.
- **Honest uncertainty**: coverage validation happens before the LLM is invoked. If evidence is missing, the system refuses to build a prompt rather than relying on the LLM to notice its absence.
- **Determinism**: same query + same graph → same Claims → same PromptPackage. The LLM's only source of variance is its own probabilistic generation.
- **Simplicity**: the prompt builder, system prompt, and provider integration depend on one interface (EvidenceBundle). No tool-use schema, no function-calling loop, no state management across retrieval calls.

## Alternatives Considered

1. **LLM tool-use**: the model retrieves evidence mid-conversation via function calls. Rejected because it shifts the retrieval decision from deterministic code to probabilistic reasoning, introducing hallucination vectors and making audit impossible.
2. **Hybrid (primary retrieve-then-generate, narrow follow-up tool)**: rejected for similar reasons — any retrieval authority granted to the LLM creates a slippery slope toward autonomous agent behaviour, which AGENTS.md explicitly prohibits.

## Consequences

- ✓ Every query's evidence is fully determined before the LLM is invoked
- ✓ Coverage validator catches missing evidence before any prompt reaches the provider
- ✓ Full audit trail: intent → strategy → plan → execution → bundle → prompt
- ⚠ Rigid — cannot handle "I need more information" follow-ups without re-running the full pipeline
- ⚠ Some retrieval decisions (which edge types to traverse, which claim types to project) must be anticipated by strategies at plan time
