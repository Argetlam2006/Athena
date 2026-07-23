"""
tests/evaluation/retrieval_stress.py — Stress-test failure scenarios.

Validates that the retrieval architecture degrades gracefully in every
failure mode identified during the architecture review.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
logging.basicConfig(stream=os.devnull, level=logging.ERROR)

from backend.retrieval.bridge import (
    RetrievalPromptBridge,
    CoverageValidationError,
)
from backend.retrieval.execution import RetrievalExecutor
from backend.retrieval.strategies import dispatch_strategy
from backend.knowledge.query import GraphQuery
from backend.knowledge.builder import GraphBuilder
from shared.schemas.retrieval import (
    Coverage,
    EdgeType,
    EntityRef,
    EvidenceBundle,
    IntentType,
    NodeType,
    StructuredIntent,
)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} — {detail}")


print("=" * 72)
print("  RETRIEVAL STRESS TEST — FAILURE SCENARIOS")
print("=" * 72)
print()

# ─── 1. Unknown player ───────────────────────────────────────────────────────
print("[Scenario] Unknown player IDs")

bridge = RetrievalPromptBridge()
intent = StructuredIntent(
    primary_type=IntentType.COMPARE_PLAYERS,
    entities={"focus_player": "99999", "compare_player": "99998"},
    raw_text="Compare two non-existent players",
)
try:
    pkg = bridge.build_prompt("Compare", intent)
    check("Completed without error (claims empty, coverage missing)", False,
          "Should have raised CoverageValidationError")
except CoverageValidationError as e:
    check("CoverageValidationError raised for non-existent players", True)
    check("Missing capabilities in error", "capability" in str(e), True)
    check("Missing archetypes in error", "archetype" in str(e), True)
except Exception as e:
    check(f"Unexpected error: {type(e).__name__}", False)

# ─── 2. Ambiguous intent (no entities) ────────────────────────────────────────
print()
print("[Scenario] Ambiguous intent (compare with no entities)")

intent_ambig = StructuredIntent(
    primary_type=IntentType.COMPARE_PLAYERS,
    entities={},
    raw_text="who is better?",
)
try:
    pkg = bridge.build_prompt("who is better?", intent_ambig)
    check("Empty comparison dispatches without crash", True)
except CoverageValidationError:
    check("Empty comparison correctly raises CoverageValidationError (expected)", True)
except Exception as e:
    check(f"Unexpected error on ambiguous intent: {type(e).__name__}", False)

# ─── 3. Unsupported intent → falls back to general ───────────────────────────
print()
print("[Scenario] Unsupported intent type")

intent_unknown = StructuredIntent(
    primary_type=IntentType.GENERAL,
    entities={},
    raw_text="What is the offside rule?",
)
strat = dispatch_strategy(intent_unknown)
check("Unsupported intent dispatches to fallback strategy", strat.name == "general")

# ─── 4. Coverage failure → prompt not built ───────────────────────────────────
print()
print("[Scenario] Coverage failure prevents prompt building")

result = bridge.build_prompt_or_none("compare?", intent_ambig)
check("build_prompt_or_none returns None on coverage failure", result is None)

# ─── 5. Bridge rejects missing capability claims ─────────────────────────────
print()
print("[Scenario] Validator rejects missing required claims")

from backend.retrieval.coverage import CoverageValidator, CoverageValidationError

validator = CoverageValidator()
bundle_bad = EvidenceBundle(
    intent=StructuredIntent(primary_type=IntentType.COMPARE_PLAYERS, entities={}),
    claims=[],
    coverage=Coverage(total_sought=2, satisfied=[], missing=["capability"]),
)
try:
    validator.validate(bundle_bad)
    check("Validator rejects missing capability", False)
except CoverageValidationError:
    check("Validator rejects missing capability", True)

# Allow optional missing
bundle_opt = EvidenceBundle(
    intent=StructuredIntent(primary_type=IntentType.COMPARE_PLAYERS, entities={}),
    claims=[],
    coverage=Coverage(total_sought=2, satisfied=["capability"], missing=["role_fit"]),
)
try:
    validator.validate(bundle_opt)
    check("Validator allows optional type (role_fit) gaps", True)
except CoverageValidationError:
    check("Validator allows optional type (role_fit) gaps", False)

# ─── 6. Empty graph → graceful query result ──────────────────────────────────
print()
print("[Scenario] Empty graph state")

gq = GraphQuery(
    edges_path=Path("data/knowledge/nonexistent_edges.parquet"),
    nodes_path=Path("data/knowledge/nonexistent_nodes.parquet"),
)
edges = gq.get_edges()
check("Empty graph returns empty list", edges == [])
check("Empty graph edges are typed list", isinstance(edges, list))

# ─── 7. Strategy registry consistency ────────────────────────────────────────
print()
print("[Scenario] Strategy registry consistency")

from backend.retrieval.strategies import list_strategies

names = list_strategies()
check(f"Strategies registered: {names}", len(names) >= 3)
check("Comparison strategy registered", "comparison" in names)
check("Replacement strategy registered", "replacement" in names)
check("General fallback registered", "general" in names)

# ─── 8. Graph determinism (rebuild consistency) ──────────────────────────────
print()
print("[Scenario] Graph determinism")

builder = GraphBuilder()
r1 = builder.build()
r2 = builder.build()
check("Deterministic graph: entity counts match", r1.entity_count == r2.entity_count)
check("Deterministic graph: edge counts match", r1.edge_count_by_type == r2.edge_count_by_type)

# ─── 9. Typed Edge invariants ────────────────────────────────────────────────
print()
print("[Scenario] Typed Edge invariants")

edges = gq.get_edges()
if not edges:
    # Rebuild and re-query
    builder.build()
    gq_real = GraphQuery()
    edges = gq_real.get_edges()

if edges:
    from shared.schemas.retrieval import Edge

    check("Edge is typed object", isinstance(edges[0], Edge))
    check("Edge has EntityRef source", isinstance(edges[0].source, EntityRef))
    check("Edge has EntityRef target", isinstance(edges[0].target, EntityRef))
    check("Edge has EdgeType", isinstance(edges[0].edge_type, EdgeType))

# ─── 10. Claim invariants ────────────────────────────────────────────────────
print()
print("[Scenario] Claim invariants under retrieval")

intent = StructuredIntent(
    primary_type=IntentType.COMPARE_PLAYERS,
    entities={"focus_player": "5503", "compare_player": "5207"},
)
try:
    pkg = bridge.build_prompt("Compare", intent)
    meta = pkg.metadata
    check("Claims produced", meta.get("retrieval_claim_count", 0) >= 2)
    check("Coverage complete", meta.get("retrieval_coverage_complete", False))
    check("Execution time recorded", meta.get("retrieval_execution_time_ms", 0) > 0)
    check("Strategy recorded", meta.get("retrieval_strategy", "") != "")
    check("Plan ID recorded", meta.get("retrieval_plan_id", "") != "")
except Exception as e:
    check(f"Successful retrieval: {type(e).__name__}", False)

# ─── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 72)
print(f"  RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} checks")
print("=" * 72)

sys.exit(0 if FAIL == 0 else 1)
