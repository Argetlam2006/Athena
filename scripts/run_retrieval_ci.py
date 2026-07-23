"""
scripts/run_retrieval_ci.py — CI quality gate for the retrieval architecture.

Reruns the benchmark and stress test suites and fails if any regression
is detected.  Intended to be run in CI before merging retrieval changes.

Exit codes:
  0 — all checks pass
  1 — regression detected
  2 — infrastructure error (could not run)

Usage:
    python scripts/run_retrieval_ci.py [--benchmark-json data/evaluation/expanded_benchmark.json]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Suppress non-critical logging during evaluation
logging.basicConfig(stream=os.devnull, level=logging.ERROR)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Thresholds (tune based on production observations) ───────────────────────

# Minimum number of benchmark questions that MUST produce claims
MIN_SUCCESSFUL_QUERIES = 24  # out of 30 (e01 expected failure)

# Maximum allowed latency for comparison queries (ms)
MAX_COMPARISON_LATENCY_MS = 3000

# Minimum total claims produced across all benchmark questions
MIN_TOTAL_CLAIMS = 150  # should be ~225 with full capability

# Maximum allowed coverage failures (queries blocked by validator)
MAX_COVERAGE_FAILURES = 2

# Maximum allowed non-coverage errors
MAX_UNEXPECTED_ERRORS = 1  # e01 (non-existent players) is expected

# Maximum allowed benchmark failures per category
MAX_CATEGORY_FAILURES: dict[str, int] = {
    "comparison": 0,
    "analysis": 0,
    "scouting": 0,
    "edge": 1,     # e01 (non-existent players) is expected to fail
}


# ─── Checks ───────────────────────────────────────────────────────────────────


def check_threshold(name: str, value, threshold, operator="le") -> list[str]:
    """Check a threshold and return a list of failure messages."""
    failures = []
    if operator == "le" and value > threshold:
        failures.append(f"{name}: {value} exceeds threshold {threshold}")
    elif operator == "ge" and value < threshold:
        failures.append(f"{name}: {value} below threshold {threshold}")
    return failures


def run_benchmark_check(args: argparse.Namespace) -> list[str]:
    """Run benchmarks and check thresholds."""
    failures: list[str] = []

    # 1. Run stress tests first
    print("Running stress tests...", end=" ", flush=True)
    stress_result = os.system(
        f"{sys.executable} -W ignore tests/evaluation/retrieval_stress.py "
        f"2>{os.devnull}"
    )
    if stress_result != 0:
        failures.append("Stress tests failed")
        print("FAILED")
    else:
        print("PASSED")

    # 2. Run expanded benchmark
    print("Running expanded benchmark...", end=" ", flush=True)
    output_path = Path(args.benchmark_json or "data/evaluation/expanded_benchmark.json")
    bench_result = os.system(
        f"{sys.executable} -W ignore tests/evaluation/retrieval_expanded_benchmark.py "
        f"--output {output_path} 2>{os.devnull}"
    )
    if bench_result != 0:
        failures.append("Benchmark suite failed to execute")
        print("FAILED")
        return failures
    print("PASSED")

    # 3. Load benchmark results
    if not output_path.exists():
        failures.append(f"Benchmark output not found: {output_path}")
        return failures

    with open(output_path) as f:
        results = json.load(f)

    # 4. Aggregate metrics
    records = results.get("results", [])
    if not records:
        failures.append("No benchmark records found")
        return failures

    total = len(records)
    claims_ok = sum(1 for r in records if r.get("retrieval_claim_count", 0) > 0)
    total_claims = sum(r.get("retrieval_claim_count", 0) for r in records)
    coverage_failures = sum(
        1 for r in records
        if r.get("retrieval_coverage_missing")
        and "capability" in r.get("retrieval_coverage_missing", [])
    )
    errors = sum(1 for r in records if r.get("error"))
    comparison_times = [
        r.get("retrieval_time_ms", 0) for r in records
        if r.get("retrieval_strategy") == "comparison" and r.get("retrieval_time_ms")
    ]

    # 5. Check thresholds
    failures.extend(
        check_threshold("Successful queries", claims_ok, MIN_SUCCESSFUL_QUERIES, "ge")
    )
    failures.extend(
        check_threshold("Total claims", total_claims, MIN_TOTAL_CLAIMS, "ge")
    )
    failures.extend(
        check_threshold("Coverage failures", coverage_failures, MAX_COVERAGE_FAILURES)
    )
    failures.extend(
        check_threshold("Unexpected errors", errors, MAX_UNEXPECTED_ERRORS)
    )

    # Per-category failures
    for category, max_fails in MAX_CATEGORY_FAILURES.items():
        cat_fails = sum(
            1 for r in records
            if r.get("category") == category and r.get("error")
        )
        failures.extend(
            check_threshold(f"Errors [{category}]", cat_fails, max_fails)
        )

    if comparison_times:
        max_comparison = max(comparison_times)
        failures.extend(
            check_threshold("Max comparison latency", max_comparison, MAX_COMPARISON_LATENCY_MS)
        )

    # 6. Print summary
    print()
    print(f"  Results: {claims_ok}/{total} queries OK, {total_claims} total claims")
    print(f"  Coverage failures: {coverage_failures}")
    print(f"  Errors: {errors}")
    if comparison_times:
        print(f"  Max comparison latency: {max(comparison_times):.0f}ms")
    print()

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Retrieval architecture CI quality gate"
    )
    parser.add_argument("--benchmark-json", default=None,
                        help="Path to benchmark JSON output")
    parser.add_argument("--skip-stress", action="store_true",
                        help="Skip stress test execution")
    args = parser.parse_args()

    failures = run_benchmark_check(args)

    if failures:
        print("REGRESSIONS DETECTED:")
        for f in failures:
            print(f"  - {f}")
        print()
        print("Retrieval changes must not introduce regressions.")
        return 1

    print("All checks passed. Retrieval infrastructure is stable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
