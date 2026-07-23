# Decision Workflows — Design

Athena's retrieval strategies produce atomic evidence (Claims) for individual analytical
questions. Higher-level football decisions require composing multiple strategies and
deterministic engines into a workflow that answers a complete football question.

This document designs four decision workflows using existing capabilities only —
no new retrieval architecture, no new reasoning layers.

---

## Workflow 1 — Replacement Planning

**Football question**: "We are losing our starting defensive midfielder. Who should we sign?"

**Composes**:
1. Fragility analysis (TeamAnalysisStrategy) — identify the structural deficit when the player is removed
2. Counterfactual analysis (CollectiveEngine) — measure capability delta without the player
3. Replacement search (ReplacementStrategy) — find candidates and evaluate restoration
4. Tactical fit (evaluate_tactical_fit) — assess each candidate against the team's playing style

**How it works today**:
- Fragility + counterfactual are already computed by the CollectiveEngine
- Replacement search uses recommend_replacement in DecisionEngine
- Tactical fit uses evaluate_tactical_fit in DecisionEngine
- Each is a separate retrieval call or engine invocation

**Gap**: No orchestrator combines these into a single response. A workflow would accept a
player_id + team_id, run all three, and return a consolidated bundle with fragility evidence,
candidates, and fit scores.

**Implementation path**: A ReplacementWorkflow function in backend/recommendation/ calls the
existing strategies and engines, then assembles a composite EvidenceBundle.
No architectural changes. Workflow lives above retrieval, not within it.

---

## Workflow 2 — Squad Audit

**Football question**: "What are the strengths, weaknesses, and structural risks of this squad?"

**Composes**:
1. Team capability analysis (TeamAnalysisStrategy) — avg squad capabilities
2. Fragility analysis (TeamAnalysisStrategy) — most irreplaceable players
3. Bottleneck analysis (CollectiveEngine) — upstream-to-downstream capability gaps
4. Concentration analysis (CollectiveEngine) — over-reliance on individual players

**How it works today**:
- Team capabilities and fragilities are already ClaimTypes with projectors
- Bottlenecks and concentration are computed by CollectiveEngine but not yet built as edges
- HAS_BOTTLENECK and HAS_CONCENTRATION edges exist in registry but need builder methods

**Gap**: 2/4 claim types exist. Bottleneck and concentration projectors need to be added
through existing extension points.

**Implementation path**: Add edge builder methods for HAS_BOTTLENECK and HAS_CONCENTRATION.
Add team_bottleneck and team_concentration ClaimTypes and projectors.
Add a SquadAuditWorkflow that runs TeamAnalysis + bottleneck + concentration queries.
All through existing registries.

---

## Workflow 3 — Tactical Fit Assessment

**Football question**: "How well does this player fit this team's tactical system?"

**Composes**:
1. Player capability analysis (PlayerAnalysisStrategy) — baseline player profile
2. Team capability analysis (TeamAnalysisStrategy) — team's tactical identity
3. Tactical fit (DecisionEngine) — evaluate_tactical_fit produces decomposed fit scores
4. Role fit claims (RoleFit projector) — per-system fit evaluation

**How it works today**:
- Player and team capabilities are retrievable
- evaluate_tactical_fit already produces decomposed scores
- Role fit claims are already projected for 5 tactical systems

**Gap**: The role fit projector evaluates against generic systems but not against the
actual team's tactical identity. The team's CollectiveIdentity has a primary_identity
field that maps to these systems.

**Implementation path**: Add an optional team_id parameter to role_fit_claims() that
filters to the team's actual tactical system. Projector change only. No new strategies.

---

## Workflow 4 — Opponent Preparation

**Football question**: "What are this opponent's weaknesses, and which of our players
are best positioned to exploit them?"

**Composes**:
1. Opponent team analysis (TeamAnalysisStrategy) — opponent capabilities + fragilities
2. Our team analysis (TeamAnalysisStrategy) — our capabilities + strengths
3. Capability gap analysis (cross-team comparison) — which opponent capabilities are weakest
4. Player-to-weakness mapping — which players have strengths matching opponent weaknesses

**Gap**: Steps 3-4 require new deterministic engine code (TeamComparison engine,
PlayerToWeaknessMapper). Not a retrieval architecture gap — a football intelligence gap.

**Implementation path**: Build TeamComparison in backend/collective/ and
PlayerToWeaknessMapper in backend/recommendation/. Register any new edge types.
No retrieval architecture changes.

---

## Design Principles

1. **Workflows live above retrieval**: A workflow calls existing strategies, engines, and
projectors. It does not introduce new retrieval primitives.

2. **Workflows produce composite bundles**: A single EvidenceBundle with claims from all
constituent strategies. CoverageValidator handles this transparently.

3. **New capabilities mean new engine code, not new architecture**: Every workflow gap
maps to a deterministic engine extension or edge builder method.

4. **Strategies remain atomic**: A workflow calls strategies; it does not modify them.
Strategies do not know they are part of a workflow.

## Gap Summary

| Workflow | Existing | Gaps | Architecture Changes |
|---|---|---|---|
| Replacement Planning | 3/3 sub-capabilities exist | Orchestrator only | None |
| Squad Audit | 2/4 claim types exist | Bottleneck + concentration projectors | None (extension points) |
| Tactical Fit Assessment | 3/3 sub-capabilities exist | Per-team identity filter | None (projector change) |
| Opponent Preparation | 2/4 sub-capabilities exist | New engine code needed | None (new engine + edge type) |
