# ADR-009 — Registry-Based Extension for Retrieval Components

**Date**: 2026-07-24
**Status**: Accepted

## Context

The architecture needed to support adding new strategies, claim types, edge types, and qualifiers over time. The question was whether these should be added by modifying existing dispatch chains (if/elif blocks) or by registering through a central declaration point.

## Decision

All extensible component categories use **registry-based dispatch**:

- **Strategies**: `_strategy_registry` — decorated with `@register_strategy`, dispatched by `dispatch_strategy()`
- **Claim types**: `CLAIM_DISPATCH` — mapping `ClaimType` enum to projector function
- **Edge types**: `EDGE_REGISTRY` — mapping `EdgeType` to source engine + function attribution
- **Qualifier rules**: `QUALIFIER_RULES` — list of `QualifierRule` declarations

Adding a new capability means adding an entry to the relevant registry. The dispatch/execution code iterates registries and never contains type-specific branching.

## Rationale

- **Discoverability**: all components of a given category are declared in one place (or one decorator). A new engineer can see all strategies by reading `_strategy_registry`.
- **Mechanical enforcement**: the registry is the source of truth. CI can verify that every `EdgeType` enum member has a registry entry, that every `ClaimType` has a projector, and that every registered strategy has a unique name.
- **No hidden branching**: the executor iterates `CLAIM_DISPATCH` rather than checking `if ct == "capability"`. A new claim type is automatically handled as soon as it is registered — no executor changes needed.
- **Self-documenting**: the registry doubles as documentation of what the system can produce.

## Consequences

- ✓ Adding a strategy, claim type, or edge type requires touching exactly the registry file + any new implementation files
- ✓ No dispatch chain needs modification for new types
- ✓ CI can verify registry completeness across all component categories
- ⚠ Registry entries are decoupled from the implementations they reference (a registry string could point to a deleted function). Mitigated by CI checks that validate function references.
