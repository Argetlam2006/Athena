"""
tests/evaluation/retrieval_expanded_benchmark.py -- Expanded benchmark suite.

Runs 30+ questions across all categories and produces detailed latency,
prompt growth, claim count, and coverage analysis.

Usage:
    python tests/evaluation/retrieval_expanded_benchmark.py [--output FILE]

Output:
    Console summary + JSON report to data/evaluation/expanded_benchmark.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(stream=os.devnull, level=logging.ERROR)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.explanation.engine import ExplanationContextEngine  # noqa: E402
from backend.explanation.prompt_builder import PromptBuilder  # noqa: E402
from backend.intelligence.store import IntelligenceStore  # noqa: E402
from backend.retrieval.bridge import RetrievalPromptBridge  # noqa: E402
from backend.retrieval.coverage import CoverageValidationError  # noqa: E402
from backend.retrieval.strategies import list_strategies  # noqa: E402
from shared.schemas.retrieval import IntentType, StructuredIntent  # noqa: E402

# --- Constants ----------------------------------------------------------------

_INTENT_MAP: dict[str, IntentType] = {
    "compare_players": IntentType.COMPARE_PLAYERS,
    "recruitment": IntentType.RECRUITMENT,
    "player_analysis": IntentType.PLAYER_ANALYSIS,
    "team_analysis": IntentType.TEAM_ANALYSIS,
    "squad_diagnosis": IntentType.SQUAD_DIAGNOSIS,
    "counterfactual": IntentType.COUNTERFACTUAL,
    "general": IntentType.GENERAL,
}

R9K = 5246  # Suarez
R7M = 5503  # Messi
CR7 = 5207  # Ronaldo
G9 = 5497   # Higuain
MBP = 3009  # Mbappe
TH = 15516  # Henry

# --- Question definition ------------------------------------------------------

@dataclass
class BenchmarkQuestion:
    id: str
    category: str
    question: str
    player_ids: list[int] | None = None
    expected_intent: str = "general"
    notes: str = ""

# --- 35 Questions -------------------------------------------------------------

QUESTIONS: list[BenchmarkQuestion] = [
    # -- Player Comparison (6) --
    BenchmarkQuestion("c01","comparison",
        "Compare Lionel Messi and Cristiano Ronaldo. What are their relative strengths and weaknesses?",
        [R7M, CR7]),
    BenchmarkQuestion("c02","comparison",
        "How does Luis Suarez compare to Gonzalo Higuain?",
        [R9K, G9]),
    BenchmarkQuestion("c03","comparison",
        "Compare Kylian Mbappe and Thierry Henry as forwards.",
        [MBP, TH]),
    BenchmarkQuestion("c04","comparison",
        "What are the key differences between Messi and Suarez?",
        [R7M, R9K]),
    BenchmarkQuestion("c05","comparison",
        "Compare Ronaldo and Mbappe in terms of attacking threat.",
        [CR7, MBP]),
    BenchmarkQuestion("c06","comparison",
        "Which player is more defensively active -- Ronaldo or Messi?",
        [R7M, CR7]),

    # -- Player Analysis (8) --
    BenchmarkQuestion("p01","analysis",
        "What are Lionel Messi's key strengths and what archetype does he fit?",
        [R7M]),
    BenchmarkQuestion("p02","analysis",
        "Analyze Cristiano Ronaldo's attacking threat and chance creation.",
        [CR7]),
    BenchmarkQuestion("p03","analysis",
        "What is Luis Suarez's capability profile?",
        [R9K]),
    BenchmarkQuestion("p04","analysis",
        "Describe Mbappe's playing style and key capabilities.",
        [MBP]),
    BenchmarkQuestion("p05","analysis",
        "What is Thierry Henry's ball progression ability?",
        [TH]),
    BenchmarkQuestion("p06","analysis",
        "Is Higuain a clinical finisher? Analyze his attacking threat.",
        [G9]),
    BenchmarkQuestion("p07","analysis",
        "What are Messi's weaknesses or development areas?",
        [R7M]),
    BenchmarkQuestion("p08","analysis",
        "How does Ronaldo compare positionally -- is he a winger or forward?",
        [CR7]),

    # -- Single-player capability questions (6) --
    BenchmarkQuestion("s01","scouting",
        "What is Messi's ball security score and what metrics drive it?",
        [R7M]),
    BenchmarkQuestion("s02","scouting",
        "How effective is Ronaldo at chance creation?",
        [CR7]),
    BenchmarkQuestion("s03","scouting",
        "Evaluate Suarez's press resistance.",
        [R9K]),
    BenchmarkQuestion("s04","scouting",
        "What is Mbappe's defensive activity rating?",
        [MBP]),
    BenchmarkQuestion("s05","scouting",
        "Analyze Henry's chance creation ability.",
        [TH]),
    BenchmarkQuestion("s06","scouting",
        "What is Higuain's pressing volume and defensive contribution?",
        [G9]),

    # -- Edge cases (6) --
    BenchmarkQuestion("e01","edge",
        "Compare two players that do not exist.",
        [99999, 99998],
        notes="Unknown player IDs -- expects graceful coverage failure"),
    BenchmarkQuestion("e02","edge",
        "What is the meaning of expected goals (xG) in football?",
        notes="General football knowledge -- no retrieval needed"),
    BenchmarkQuestion("e03","edge",
        "Explain the offside rule in simple terms.",
        notes="General football knowledge -- no retrieval needed"),
    BenchmarkQuestion("e04","edge",
        "What does 'false nine' mean tactically?",
        notes="General football knowledge -- no retrieval needed"),
    BenchmarkQuestion("e05","edge",
        "Compare Messi with a non-existent AI-generated player.",
        [R7M, 77777],
        notes="One real, one fake -- partial coverage expected"),
    BenchmarkQuestion("e06","edge",
        "Tell me about this football team.",
        notes="Ambiguous -- no entities provided"),

    # -- Recruitment / replacement (3) --
    BenchmarkQuestion("r01","recruitment",
        "Who could replace Messi at Barcelona?",
        [R7M],
        expected_intent="recruitment"),
    BenchmarkQuestion("r02","recruitment",
        "Find a replacement for Ronaldo at Juventus.",
        [CR7],
        expected_intent="recruitment"),
    BenchmarkQuestion("r03","recruitment",
        "What type of player would best complement Suarez up front?",
        [R9K],
        expected_intent="recruitment"),

    # -- Cross-cohort (2) --
    BenchmarkQuestion("x01","squad",
        "Which La Liga forwards have the best ball progression?",
        notes="Cross-cohort -- requires position+competition filtering,"
              " not directly supported yet"),
]


@dataclass
class PerfResult:
    """Performance metrics for a single pipeline run."""
    prompt_size_bytes: int = 0
    retrieval_time_ms: float = 0.0
    coverage_satisfied: list[str] = field(default_factory=list)
    coverage_missing: list[str] = field(default_factory=list)
    coverage_complete: bool = False
    claim_count: int = 0
    strategy: str = ""
    plan_id: str = ""
    entity_count: int = 0
    error: str | None = None
    context_type: str = ""


@dataclass
class QuestionResult:
    id: str
    category: str
    question_preview: str
    baseline: PerfResult = field(default_factory=PerfResult)
    retrieval: PerfResult = field(default_factory=PerfResult)


def run_baseline(q: BenchmarkQuestion) -> PerfResult:
    """Simulate existing Ask Athena pipeline (no retrieval)."""
    ctx_engine = ExplanationContextEngine()
    builder = PromptBuilder()
    store = IntelligenceStore()

    context = None
    context_type = "general"
    if q.player_ids and len(q.player_ids) == 1:
        pid = q.player_ids[0]
        profile = store.get_player(pid)
        if profile:
            context = ctx_engine.get_player_context(profile)
            context_type = "player"
    elif q.player_ids and len(q.player_ids) >= 2:
        profiles = [store.get_player(pid) for pid in q.player_ids[:2]]
        profiles = [p for p in profiles if p is not None]
        if len(profiles) >= 2:
            from backend.recommendation.comparison import compare_players
            result = compare_players(profiles)
            context = ctx_engine.get_comparison_context(result)
            context_type = "comparison"

    prompt_pkg = builder.build(q.question, context, context_type)
    return PerfResult(
        prompt_size_bytes=len(prompt_pkg.serialized_context),
        context_type=context_type,
        error=None,
    )


def run_retrieval(q: BenchmarkQuestion, bridge: RetrievalPromptBridge) -> PerfResult:
    """Run retrieval pipeline with detailed timing."""
    # Auto-detect intent from player IDs (same logic as baseline)
    expected_intent = q.expected_intent
    if expected_intent == "general" and q.player_ids:
        expected_intent = "compare_players" if len(q.player_ids) >= 2 else "player_analysis"
    intent_type = _INTENT_MAP.get(expected_intent, IntentType.GENERAL)
    entities: dict[str, str] = {}
    if q.player_ids:
        if len(q.player_ids) == 1:
            entities["focus_player"] = str(q.player_ids[0])
        elif len(q.player_ids) >= 2:
            entities["focus_player"] = str(q.player_ids[0])
            entities["compare_player"] = str(q.player_ids[1])

    intent = StructuredIntent(
        primary_type=intent_type,
        entities=entities,
        raw_text=q.question,
    )

    start = time.perf_counter()
    try:
        pkg = bridge.build_prompt(q.question, intent)
        elapsed = (time.perf_counter() - start) * 1000
    except CoverageValidationError as e:
        return PerfResult(
            error=f"CoverageValidationError: {e}",
            retrieval_time_ms=(time.perf_counter() - start) * 1000,
        )
    except Exception as e:
        return PerfResult(
            error=f"{type(e).__name__}: {e}",
            retrieval_time_ms=(time.perf_counter() - start) * 1000,
        )

    meta = pkg.metadata
    return PerfResult(
        prompt_size_bytes=meta.get("context_size_bytes", 0),
        retrieval_time_ms=elapsed,
        coverage_satisfied=meta.get("retrieval_coverage_satisfied", []),
        coverage_missing=meta.get("retrieval_coverage_missing", []),
        coverage_complete=meta.get("retrieval_coverage_complete", False),
        claim_count=meta.get("retrieval_claim_count", 0),
        strategy=meta.get("retrieval_strategy", ""),
        plan_id=meta.get("retrieval_plan_id", ""),
        entity_count=meta.get("retrieval_entity_count", 0),
    )


def run_benchmark() -> list[QuestionResult]:
    """Run all questions through both pipelines."""
    bridge = RetrievalPromptBridge()
    results: list[QuestionResult] = []

    for q in QUESTIONS:
        baseline = run_baseline(q)
        retrieval = run_retrieval(q, bridge)
        results.append(QuestionResult(
            id=q.id, category=q.category,
            question_preview=q.question[:80],
            baseline=baseline, retrieval=retrieval,
        ))
    return results


def print_report(results: list[QuestionResult]) -> None:
    """Print formatted report with summary and per-question analysis."""
    n = len(results)
    base_sizes = [r.baseline.prompt_size_bytes for r in results]
    ret_sizes = [r.retrieval.prompt_size_bytes for r in results if r.retrieval.error is None]
    ret_times = [r.retrieval.retrieval_time_ms for r in results]
    base_errors = sum(1 for r in results if r.baseline.error)
    ret_errors = sum(1 for r in results if r.retrieval.error)
    ret_coverage_ok = sum(1 for r in results if r.retrieval.coverage_complete and r.retrieval.error is None)
    ret_coverage_gaps = sum(1 for r in results if not r.retrieval.coverage_complete and r.retrieval.error is None)
    successful_ret = [r for r in results if r.retrieval.error is None and r.retrieval.claim_count > 0]

    print()
    print("=" * 72)
    print("  RETRIEVAL BENCHMARK -- EXPANDED REPORT")
    print("=" * 72)
    print(f"  Questions: {n}")
    print(f"  Strategies: {list_strategies()}")
    print()

    # Aggregates
    print("  -- Aggregates --")
    print(f"    {'Metric':<45} {'Baseline':>12} {'Retrieval':>12}")
    print(f"    {'-'*45} {'-'*12} {'-'*12}")
    avg_base = sum(base_sizes) / n if n > 0 else 0
    avg_ret = sum(ret_sizes) / len(ret_sizes) if ret_sizes else 0
    max_base = max(base_sizes) if base_sizes else 0
    max_ret = max(ret_sizes) if ret_sizes else 0
    print(f"    {'Average prompt size (bytes)':<45} {avg_base:>12.0f} {avg_ret:>12.0f}")
    print(f"    {'Max prompt size (bytes)':<45} {max_base:>12,d} {max_ret:>12,d}")
    print(f"    {'Errors':<45} {base_errors:>12} {ret_errors:>12}")
    print(f"    {'Coverage OK (claims produced)':<45} {'N/A':>12} {ret_coverage_ok:>12}")
    print(f"    {'Coverage gaps (empty results)':<45} {'N/A':>12} {ret_coverage_gaps:>12}")

    avg_ret_time = sum(ret_times) / n if n > 0 else 0
    max_ret_time = max(ret_times) if ret_times else 0
    print(f"    {'Average retrieval time (ms)':<45} {'N/A':>12} {avg_ret_time:>12.1f}")
    print(f"    {'Max retrieval time (ms)':<45} {'N/A':>12} {max_ret_time:>12.1f}")
    if successful_ret:
        avg_claims = sum(r.retrieval.claim_count for r in successful_ret) / len(successful_ret)
        total_claims = sum(r.retrieval.claim_count for r in successful_ret)
        print(f"    {'Average claims (successful queries)':<45} {'N/A':>12} {avg_claims:>12.1f}")
        print(f"    {'Total claims':<45} {'N/A':>12} {total_claims:>12}")

    # Prompt growth
    print()
    print("  -- Prompt Growth Analysis --")
    paired = [(r.baseline.prompt_size_bytes, r.retrieval.prompt_size_bytes) for r in results
              if r.baseline.error is None and r.retrieval.error is None]
    if paired:
        deltas = [r - b for b, r in paired]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0
        max_delta = max(deltas) if deltas else 0
        growth_pct = ((sum(r for _, r in paired) / sum(b for b, _ in paired)) - 1) * 100 if sum(b for b, _ in paired) > 0 else 0
        print(f"    Avg prompt delta: {avg_delta:+.0f} bytes")
        print(f"    Max prompt delta: {max_delta:+.0f} bytes")
        print(f"    Total growth: {growth_pct:+.1f}%")
        # By comparison vs non-comparison
        comp_deltas = [r.retrieval.prompt_size_bytes - r.baseline.prompt_size_bytes for r in results
                       if r.category == "comparison" and r.baseline.error is None and r.retrieval.error is None]
        if comp_deltas:
            avg_comp = sum(comp_deltas) / len(comp_deltas)
            print(f"    Comparison avg delta: {avg_comp:+.0f} bytes (richer evidence)")
        single_deltas = [r.retrieval.prompt_size_bytes - r.baseline.prompt_size_bytes for r in results
                         if r.category in ("analysis", "scouting") and r.baseline.error is None and r.retrieval.error is None]
        if single_deltas:
            avg_single = sum(single_deltas) / len(single_deltas)
            print(f"    Single-player avg delta: {avg_single:+.0f} bytes")

    # Coverage analysis
    print()
    print("  -- Coverage Analysis (retrieval) --")
    all_types = set()
    for r in results:
        all_types.update(r.retrieval.coverage_satisfied)
        all_types.update(r.retrieval.coverage_missing)
    print(f"    Claim types seen: {sorted(all_types)}")
    print(f"    Full coverage: {ret_coverage_ok}/{n} queries")
    print(f"    Coverage gaps: {ret_coverage_gaps}/{n} queries")

    # Per-question
    print()
    print("  -- Per-Question Detail --")
    for r in results:
        delta = r.retrieval.prompt_size_bytes - r.baseline.prompt_size_bytes
        sign = "+" if delta > 0 else ""
        status = "OK" if r.retrieval.error is None and r.retrieval.claim_count > 0 else (
            "GAP" if r.retrieval.error is None and r.retrieval.claim_count == 0 else "ERR"
        )
        print(f"    [{r.id:5s}] {r.category:12s} | "
              f"base={r.baseline.prompt_size_bytes:>6}B "
              f"ret={r.retrieval.prompt_size_bytes:>6}B "
              f"({sign}{abs(delta):>5}B) | "
              f"claims={r.retrieval.claim_count:>2} "
              f"time={r.retrieval.retrieval_time_ms:>7.1f}ms "
              f"strat={r.retrieval.strategy:>10s} "
              f"cov={str(r.retrieval.coverage_missing or 'full'):>12s} "
              f"[{status}]")
        if r.retrieval.error:
            print(f"                    ERROR: {r.retrieval.error[:80]}")

    print()
    print("=" * 72)
    print("  RETRIEVAL READINESS")
    print("=" * 72)
    ready = ret_errors == 0 and ret_coverage_ok > 0
    if ready:
        print(f"  v All {n} questions completed without unexpected errors")
    else:
        print(f"  ! {ret_errors} errors, {ret_coverage_gaps} coverage gaps")
    growth_warning = avg_ret > avg_base * 2 if paired else False
    if growth_warning:
        print("  ! Prompt sizes have grown significantly -- consider claim pruning")
    else:
        print("  v Prompt sizes within acceptable range")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/evaluation/expanded_benchmark.json")
    args = parser.parse_args()

    results = run_benchmark()

    # Write JSON report
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({
            "total_questions": len(results),
            "results": [
                {
                    "id": r.id, "category": r.category,
                    "baseline_prompt_bytes": r.baseline.prompt_size_bytes,
                    "retrieval_prompt_bytes": r.retrieval.prompt_size_bytes,
                    "retrieval_claim_count": r.retrieval.claim_count,
                    "retrieval_time_ms": r.retrieval.retrieval_time_ms,
                    "retrieval_strategy": r.retrieval.strategy,
                    "retrieval_coverage_satisfied": r.retrieval.coverage_satisfied,
                    "retrieval_coverage_missing": r.retrieval.coverage_missing,
                    "error": r.retrieval.error,
                }
                for r in results
            ],
        }, f, indent=2, default=str)

    print_report(results)
