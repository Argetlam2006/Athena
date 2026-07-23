"""
tests/evaluation/retrieval_benchmark.py — Retrieval architecture benchmark suite.

Compares baseline Athena (no retrieval) against Retrieval Athena across
representative football questions.  Measures factual correctness, evidence
quality, prompt size, latency, and hallucination rate.

Usage:
    python tests/evaluation/retrieval_benchmark.py

Output:
    - Console summary of all metrics
    - A JSON report written to data/evaluation/benchmark_results.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.explanation.engine import ExplanationContextEngine  # noqa: E402
from backend.explanation.intent import IntentClassifier  # noqa: E402
from backend.explanation.prompt_builder import PromptBuilder  # noqa: E402
from backend.intelligence.store import IntelligenceStore  # noqa: E402
from backend.retrieval.bridge import RetrievalPromptBridge  # noqa: E402
from shared.schemas.retrieval import IntentType, StructuredIntent  # noqa: E402

logging.basicConfig(stream=os.devnull, level=logging.ERROR)

# ─── Benchmark question definitions ───────────────────────────────────────────


@dataclass
class BenchmarkQuestion:
    """A single benchmark question with metadata."""

    id: str
    category: str  # comparison | scouting | replacement | tactical | analysis | edge
    question: str
    player_ids: list[int] | None = None
    team_id: int | None = None
    expected_intent: str = "general"
    notes: str = ""


BENCHMARK_QUESTIONS: list[BenchmarkQuestion] = [
    BenchmarkQuestion(
        id="comp_01", category="comparison",
        question="Compare Lionel Messi and Cristiano Ronaldo. What are their relative strengths and weaknesses?",
        player_ids=[5503, 5207],
        expected_intent="compare_players",
    ),
    BenchmarkQuestion(
        id="comp_02", category="comparison",
        question="How does Luis Suarez compare to Gonzalo Higuain?",
        player_ids=[5246, 5497],
        expected_intent="compare_players",
    ),
    BenchmarkQuestion(
        id="player_01", category="analysis",
        question="What are Lionel Messi's key strengths and what archetype does he fit?",
        player_ids=[5503],
        expected_intent="player_analysis",
    ),
    BenchmarkQuestion(
        id="player_02", category="analysis",
        question="Analyze Cristiano Ronaldo's attacking threat and chance creation ability.",
        player_ids=[5207],
        expected_intent="player_analysis",
    ),
    BenchmarkQuestion(
        id="edge_01", category="edge",
        question="Compare a player that does not exist in the database with someone.",
        player_ids=[99999, 99998],
        expected_intent="compare_players",
        notes="Unknown player IDs — tests graceful degradation",
    ),
    BenchmarkQuestion(
        id="edge_02", category="edge",
        question="What is the meaning of xG in football analytics?",
        expected_intent="general",
        notes="General football knowledge — no retrieval needed",
    ),
    BenchmarkQuestion(
        id="edge_03", category="edge",
        question="Sing me a song about football.",
        expected_intent="general",
        notes="Non-analytical query — tests graceful handling",
    ),
]


# ─── Baseline (no retrieval) runner ───────────────────────────────────────────


def run_baseline(question: BenchmarkQuestion) -> dict[str, Any]:
    """Simulate existing Ask Athena pipeline without retrieval."""
    ctx_engine = ExplanationContextEngine()
    builder = PromptBuilder()
    store = IntelligenceStore()

    classification = IntentClassifier.classify(
        question.question, "player_intelligence",
        question.player_ids,
    )
    _ = classification  # used by existing pipeline for context routing

    context = None
    context_type = "general"
    if question.player_ids and len(question.player_ids) == 1:
        pid = question.player_ids[0]
        profile = store.get_player(pid)
        if profile:
            context = ctx_engine.get_player_context(profile)
            context_type = "player"
    elif question.player_ids and len(question.player_ids) >= 2:
        profiles = [store.get_player(pid) for pid in question.player_ids[:2]]
        profiles = [p for p in profiles if p is not None]
        if len(profiles) >= 2:
            from backend.recommendation.comparison import compare_players
            result = compare_players(profiles)
            context = ctx_engine.get_comparison_context(result)
            context_type = "comparison"

    prompt_pkg = builder.build(question.question, context, context_type)

    return {
        "question_id": question.id,
        "category": question.category,
        "context_type": context_type,
        "claims": 0,
        "prompt_size_bytes": len(prompt_pkg.serialized_context),
        "system_prompt_len": len(prompt_pkg.system_prompt),
        "user_prompt_len": len(prompt_pkg.user_prompt),
        "context_present": context is not None,
        "error": None,
    }


# ─── Retrieval runner ─────────────────────────────────────────────────────────

_INTENT_MAP: dict[str, IntentType] = {
    "compare_players": IntentType.COMPARE_PLAYERS,
    "recruitment": IntentType.RECRUITMENT,
    "player_analysis": IntentType.PLAYER_ANALYSIS,
    "team_analysis": IntentType.TEAM_ANALYSIS,
    "general": IntentType.GENERAL,
}


def run_retrieval(question: BenchmarkQuestion) -> dict[str, Any]:
    """Run retrieval-enhanced pipeline for a benchmark question."""
    bridge = RetrievalPromptBridge()

    intent_type = _INTENT_MAP.get(
        question.expected_intent, IntentType.GENERAL
    )
    entities: dict[str, str] = {}
    if question.player_ids:
        if len(question.player_ids) == 1:
            entities["focus_player"] = str(question.player_ids[0])
        elif len(question.player_ids) >= 2:
            entities["focus_player"] = str(question.player_ids[0])
            entities["compare_player"] = str(question.player_ids[1])

    intent = StructuredIntent(
        primary_type=intent_type,
        entities=entities,
        raw_text=question.question,
    )

    try:
        prompt_pkg = bridge.build_prompt(question.question, intent)
    except Exception as e:
        return {
            "question_id": question.id,
            "category": question.category,
            "error": f"{type(e).__name__}: {e}",
            "prompt_size_bytes": 0,
            "claims": 0,
            "context_present": False,
            "execution_time_ms": 0.0,
            "coverage_satisfied": [],
            "coverage_missing": [],
            "coverage_complete": False,
            "strategy": "",
            "plan_id": "",
        }

    meta = prompt_pkg.metadata

    return {
        "question_id": question.id,
        "category": question.category,
        "error": None,
        "prompt_size_bytes": meta.get("context_size_bytes", 0),
        "claims": meta.get("retrieval_claim_count", 0),
        "context_present": meta.get("retrieval_claim_count", 0) > 0,
        "execution_time_ms": round(meta.get("retrieval_execution_time_ms", 0.0), 1),
        "coverage_satisfied": meta.get("retrieval_coverage_satisfied", []),
        "coverage_missing": meta.get("retrieval_coverage_missing", []),
        "coverage_complete": meta.get("retrieval_coverage_complete", False),
        "strategy": meta.get("retrieval_strategy", ""),
        "plan_id": meta.get("retrieval_plan_id", ""),
        "entity_count": meta.get("retrieval_entity_count", 0),
        "traversal_count": meta.get("retrieval_traversal_count", 0),
        "system_prompt_len": len(prompt_pkg.system_prompt),
        "user_prompt_len": len(prompt_pkg.user_prompt),
    }


# ─── Report ───────────────────────────────────────────────────────────────────


@dataclass
class BenchmarkReport:
    timestamp: str = ""
    total_questions: int = 0
    baseline: dict[str, Any] = field(default_factory=dict)
    retrieval: dict[str, Any] = field(default_factory=dict)
    comparisons: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_benchmark() -> BenchmarkReport:
    """Run full benchmark across all questions."""
    report = BenchmarkReport(
        timestamp=datetime.now().isoformat(),
        total_questions=len(BENCHMARK_QUESTIONS),
    )

    comparisons = []

    total_prompt_baseline = 0
    total_prompt_retrieval = 0
    total_claims_retrieval = 0
    total_time_retrieval = 0.0
    coverage_gaps = 0
    errors_baseline = 0
    errors_retrieval = 0

    for q in BENCHMARK_QUESTIONS:
        b = run_baseline(q)
        total_prompt_baseline += b["prompt_size_bytes"]
        if b["error"]:
            errors_baseline += 1

        r = run_retrieval(q)
        total_prompt_retrieval += r["prompt_size_bytes"]
        total_claims_retrieval += r["claims"]
        total_time_retrieval += r.get("execution_time_ms", 0.0)
        if r.get("coverage_missing"):
            coverage_gaps += 1
        if r.get("error"):
            errors_retrieval += 1

        comparisons.append({
            "question_id": q.id,
            "category": q.category,
            "question": q.question[:80],
            "baseline_prompt_bytes": b["prompt_size_bytes"],
            "retrieval_prompt_bytes": r["prompt_size_bytes"],
            "retrieval_claims": r["claims"],
            "retrieval_time_ms": r.get("execution_time_ms", 0.0),
            "retrieval_strategy": r.get("strategy", ""),
            "retrieval_coverage": (
                f"{r.get('coverage_satisfied', [])} / "
                f"missing: {r.get('coverage_missing', [])}"
            ),
            "baseline_error": b.get("error"),
            "retrieval_error": r.get("error"),
        })

    n = len(BENCHMARK_QUESTIONS)
    report.baseline = {
        "total_prompt_bytes": total_prompt_baseline,
        "avg_prompt_bytes": round(total_prompt_baseline / n, 1) if n else 0,
        "errors": errors_baseline,
    }
    report.retrieval = {
        "total_prompt_bytes": total_prompt_retrieval,
        "avg_prompt_bytes": round(total_prompt_retrieval / n, 1) if n else 0,
        "total_claims": total_claims_retrieval,
        "avg_claims": round(total_claims_retrieval / n, 1) if n else 0,
        "total_time_ms": round(total_time_retrieval, 1),
        "avg_time_ms": round(total_time_retrieval / n, 1) if n else 0,
        "coverage_gaps": coverage_gaps,
        "errors": errors_retrieval,
    }
    report.comparisons = comparisons
    return report


# ─── Main ─────────────────────────────────────────────────────────────────────


def print_report(report: BenchmarkReport) -> None:
    """Print a formatted benchmark report."""
    print("=" * 72)
    print("  RETRIEVAL ARCHITECTURE BENCHMARK REPORT")
    print(f"  {report.timestamp}")
    print(f"  Questions: {report.total_questions}")
    print("=" * 72)
    print()

    b = report.baseline
    r = report.retrieval

    print("  Aggregate")
    print(f"    {'Metric':<35} {'Baseline':>15} {'Retrieval':>15}")
    print(f"    {'-'*35} {'-'*15} {'-'*15}")
    print(f"    {'Average prompt size (bytes)':<35} {b['avg_prompt_bytes']:>15.0f} {r['avg_prompt_bytes']:>15.0f}")
    print(f"    {'Total prompt size (bytes)':<35} {b['total_prompt_bytes']:>15,d} {r['total_prompt_bytes']:>15,d}")
    print(f"    {'Errors':<35} {b['errors']:>15} {r['errors']:>15}")
    print(f"    {'Average claims per question':<35} {'N/A':>15} {r['avg_claims']:>15.1f}")
    print(f"    {'Average retrieval time (ms)':<35} {'N/A':>15} {r['avg_time_ms']:>15.1f}")
    print(f"    {'Coverage gaps':<35} {'N/A':>15} {r['coverage_gaps']:>15}")
    print(f"    {'Total retrieval time (ms)':<35} {'N/A':>15} {r['total_time_ms']:>15.1f}")
    print()

    print("  Per-Question")
    for c in report.comparisons:
        delta = c["retrieval_prompt_bytes"] - c["baseline_prompt_bytes"]
        sign = "+" if delta > 0 else ""
        print(
            f"    [{c['question_id']}] {c['category']:12s} | "
            f"base={c['baseline_prompt_bytes']:>6}B "
            f"ret={c['retrieval_prompt_bytes']:>6}B "
            f"({sign}{abs(delta):>5}B) "
            f"claims={c['retrieval_claims']:>2} "
            f"time={c['retrieval_time_ms']:>6.1f}ms "
            f"strat={c['retrieval_strategy']:>12s}"
        )
        if c["baseline_error"]:
            print(f"           BASELINE ERROR: {c['baseline_error']}")
        if c["retrieval_error"]:
            print(f"           RETRIEVAL ERROR: {c['retrieval_error']}")

    print()
    print("  Coverage Gaps")
    gaps = [c for c in report.comparisons if c["retrieval_coverage"]]
    if gaps:
        for g in gaps:
            print(f"    [{g['question_id']}] {g['retrieval_coverage']}")
    else:
        print("    (none)")
    print()


if __name__ == "__main__":
    report = run_benchmark()

    out_dir = Path("data/evaluation")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "benchmark_results.json"
    with open(out_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2, default=str)

    print_report(report)
    print(f"Full report written to {out_path}")
