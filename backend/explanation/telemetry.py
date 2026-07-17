"""
backend/explanation/telemetry.py - Telemetry for the Explanation Layer.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class ExplanationTelemetry:
    """Records metrics for an explanation generation request."""

    provider: str
    model: str
    prompt_version: str

    context_size_bytes: int

    latency_ms: float
    streaming_duration_ms: float

    tokens_prompt: int
    tokens_completion: int

    status: str  # "success", "error", "timeout"
    error_message: str | None = None
    retries: int = 0

    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    @property
    def tokens_per_second(self) -> float:
        if self.streaming_duration_ms <= 0:
            return 0.0
        return (self.tokens_completion / self.streaming_duration_ms) * 1000.0


def record_telemetry(metrics: ExplanationTelemetry) -> None:
    """
    Records the telemetry payload.
    For this implementation, we simply log it. No conversation contents are stored.
    """
    logger.info(
        f"[TELEMETRY] Provider={metrics.provider} Model={metrics.model} "
        f"PromptVer={metrics.prompt_version} Status={metrics.status} "
        f"Latency={metrics.latency_ms:.1f}ms StreamDur={metrics.streaming_duration_ms:.1f}ms "
        f"Tokens/sec={metrics.tokens_per_second:.1f} ContextSize={metrics.context_size_bytes}B"
    )
