"""
backend/retrieval/debug.py — Developer diagnostics mode.

Provides a structured debug report for every retrieval-assisted request.
Only active when ATHENA_DEBUG=true — isolated from normal users.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DebugTrace:
    """Complete diagnostic trace for one retrieval request."""

    # Input
    raw_query: str = ""
    normalized_query: str = ""

    # Intent
    intent_type: str = ""
    resolved_entities: dict[str, str] = field(default_factory=dict)

    # Conversation context
    context_last_intent: str = ""
    context_comparison_pair: str = ""
    context_current_player: str = ""

    # Retrieval
    strategy: str = ""
    plan_id: str = ""
    plan_step_count: int = 0
    entity_count: int = 0
    traversal_count: int = 0
    traversal_summary: list[str] = field(default_factory=list)

    # Execution
    claim_count: int = 0
    claim_types: list[str] = field(default_factory=list)
    projected_claims: list[str] = field(default_factory=list)
    evidence_bundle_stats: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0

    # Coverage
    coverage_satisfied: list[str] = field(default_factory=list)
    coverage_missing: list[str] = field(default_factory=list)
    coverage_complete: bool = False

    # Prompt
    context_size_bytes: int = 0
    prompt_total_chars: int = 0

    # Outcome
    success: bool = False
    error: str = ""
    error_type: str = ""
    outcome: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v}


# ─── Singleton ───────────────────────────────────────────────────────────────

_last_trace: DebugTrace | None = None


def get_last_trace() -> DebugTrace | None:
    """Get the most recent debug trace."""
    global _last_trace
    return _last_trace


def record_trace(trace: DebugTrace) -> None:
    """Store a debug trace for the last request."""
    global _last_trace
    _last_trace = trace


def is_debug_enabled() -> bool:
    """Check if developer debug mode is active."""
    return os.getenv("ATHENA_DEBUG", "").lower() in ("true", "1", "yes")


def format_debug_report(trace: DebugTrace) -> str:
    """Format a debug trace as a readable string."""
    lines = [
        "=" * 60,
        "ATHENA DEBUG REPORT",
        "=" * 60,
        "",
        f"  Query:          {trace.raw_query}",
        f"  Normalized:     {trace.normalized_query}",
        f"  Intent:         {trace.intent_type}",
        f"  Entities:       {trace.resolved_entities}",
        "",
        "  Context:",
        f"    Last intent:   {trace.context_last_intent}",
        f"    Comparison:    {trace.context_comparison_pair}",
        f"    Current:       {trace.context_current_player}",
        "",
        "  Retrieval:",
        f"    Strategy:      {trace.strategy}",
        f"    Plan ID:       {trace.plan_id}",
        f"    Plan steps:    {trace.plan_step_count}",
        f"    Entities:      {trace.entity_count}",
        f"    Traversals:    {trace.traversal_count}",
        f"    Summary:       {trace.traversal_summary}",
        "",
        "  Execution:",
        f"    Claims:        {trace.claim_count}",
        f"    Claim types:   {trace.claim_types}",
        f"    Projected:     {trace.projected_claims}",
        f"    Bundle:        {trace.evidence_bundle_stats}",
        f"    Time:          {trace.execution_time_ms:.1f}ms",
        "",
        "  Coverage:",
        f"    Satisfied:     {trace.coverage_satisfied}",
        f"    Missing:       {trace.coverage_missing}",
        f"    Complete:      {trace.coverage_complete}",
        "",
        "  Prompt:",
        f"    Context size:  {trace.context_size_bytes} bytes",
        f"    Total chars:   {trace.prompt_total_chars}",
        "",
        "  Outcome:",
        f"    Success:       {trace.success}",
        f"    Outcome:       {trace.outcome}",
        f"    Error:         {trace.error_type}: {trace.error}" if trace.error else "",
        "=" * 60,
    ]
    return "\n".join(line for line in lines if line)
