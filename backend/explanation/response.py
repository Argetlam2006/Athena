"""
backend/explanation/response.py — Response Models for the Explanation Layer.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ExplanationResponse:
    """
    Standardized response format from an ExplanationProvider.
    """

    generated_text: str
    provider: str
    model: str

    latency_ms: float
    token_usage: dict[str, int]  # e.g. {"prompt": X, "completion": Y, "total": Z}
    finish_reason: str

    confidence: str  # e.g., "high", "medium", "low"
    citations: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))
