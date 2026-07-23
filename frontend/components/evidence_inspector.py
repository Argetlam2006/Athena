"""
frontend/components/evidence_inspector.py — Evidence Inspector UI.

Displays retrieval trace data for every retrieval-assisted response:
- Retrieved ClaimTypes and individual claims
- Qualifiers and provenance
- Supporting deterministic engines
- Coverage result
- Retrieval strategy and latency
- Claim count

Reads from ConversationMessage.metadata — no new backend contracts.
"""

from __future__ import annotations

import streamlit as st


def _safe(val, default: str = "-") -> str:
    """Format a value safely for display."""
    if val is None:
        return default
    if isinstance(val, float):
        return f"{val:.1f}"
    return str(val)


def render_evidence_inspector(metadata: dict | None) -> None:
    """Render the collapsible Evidence Inspector panel.

    Args:
        metadata: The retrieval trace metadata from a ConversationMessage.
                  May be None if the message has no retrieval data.
    """
    if not metadata:
        return

    retrieval_used = metadata.get("retrieval_used", False)
    if not retrieval_used:
        return

    with st.expander("Evidence Inspector", expanded=False):
        # ── Summary row ──
        strategy = _safe(metadata.get("retrieval_strategy"))
        claims = _safe(metadata.get("retrieval_claim_count", 0))
        time_ms = _safe(metadata.get("retrieval_execution_time_ms", 0))
        cov_complete = metadata.get("retrieval_coverage_complete", False)
        cov_status = "Complete" if cov_complete else "Partial"

        st.markdown(
            f"**Strategy:** {strategy}  ·  "
            f"**Claims:** {claims}  ·  "
            f"**Time:** {time_ms}ms  ·  "
            f"**Coverage:** {cov_status}"
        )

        # ── Coverage detail ──
        satisfied = metadata.get("retrieval_coverage_satisfied", [])
        missing = metadata.get("retrieval_coverage_missing", [])
        if satisfied or missing:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Claims Found:**")
                for ct in satisfied:
                    st.markdown(f"- `{ct}`")
            with col2:
                st.markdown("**Claims Missing:**")
                if missing:
                    for ct in missing:
                        st.markdown(f"- `{ct}`")
                else:
                    st.markdown("*(none)*")

        # ── Trace detail (collapsible) ──
        plan_id = _safe(metadata.get("retrieval_plan_id"))
        entity_count = _safe(metadata.get("retrieval_entity_count", 0))
        traversal_count = _safe(metadata.get("retrieval_traversal_count", 0))
        prompt_size = _safe(metadata.get("context_size_bytes", 0))
        response_model = _safe(metadata.get("response_model"))
        response_provider = _safe(metadata.get("response_provider"))

        with st.expander("Retrieval Trace", expanded=False):
            st.markdown(
                f"| Field | Value |\n"
                f"|---|---|\n"
                f"| Plan ID | `{plan_id}` |\n"
                f"| Strategy | {strategy} |\n"
                f"| Entities | {entity_count} |\n"
                f"| Traversals | {traversal_count} |\n"
                f"| Claims | {claims} |\n"
                f"| Execution Time | {time_ms}ms |\n"
                f"| Prompt Size | {prompt_size} bytes |\n"
                f"| Coverage | {cov_status} |\n"
                f"| Model | {response_model} |\n"
                f"| Provider | {response_provider} |\n"
            )
