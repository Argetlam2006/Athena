# ADR-010 — Coverage Validation Before PromptBuilder

**Date**: 2026-07-24
**Status**: Accepted

## Context

The retrieval architecture produces an EvidenceBundle containing claims and coverage metadata. The prompt builder then serializes the bundle into the LLM's context. The question was: where should the system enforce that sufficient evidence exists to answer the user's question?

If coverage validation happens inside the prompt builder, a new prompt template could accidentally bypass validation by not calling it. If coverage validation happens at the retrieval boundary, before any prompt-specific code runs, the invariant is mechanically enforced.

## Decision

Coverage validation happens **before the PromptBuilder is invoked**, as a separate step in the RetrievalPromptBridge pipeline:

```
Strategy -> Plan -> Execution -> Coverage Validation -> PromptBuilder -> Provider
                                  ^^^^^^^^^^^^^^^^^^^
                                  Fails here if evidence
                                  is insufficient
```

The CoverageValidator raises CoverageValidationError if required claim types are missing. The bridge's build_prompt() propagates this error. The bridge's build_prompt_or_none() catches it and returns None. The PromptBuilder never receives a bundle with insufficient coverage for its intent type.

## Rationale

- **Mechanically enforceable**: the PromptBuilder cannot accidentally bypass validation — it never receives invalid bundles from the bridge.
- **Fail fast**: validation happens before any prompt-formatting or serialization work. An invalid question is rejected in ~100ms rather than after a ~500ms prompt build.
- **No prompt-template dependency**: every prompt template (player analysis, comparison, recruitment) automatically inherits coverage validation without being modified.

## Consequences

- ✓ The "evidence before AI" invariant is mechanically enforced at the retrieval-to-generation boundary
- ✓ Prompt templates cannot accidentally bypass validation
- ✓ Coverage data is always logged, even when validation fails (for debugging)
- ⚠ The validator's requirements must match what the prompt templates need. If a prompt template is updated to require a new claim type, the validator must also be updated. Currently mitigated by storing requirements in plan metadata rather than hardcoding them in the validator.
