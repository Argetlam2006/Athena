"""
backend/explanation/providers/claude_provider.py — Anthropic Claude Provider.
"""

import os
import time
from collections.abc import Generator

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.base import ExplanationProvider
from backend.explanation.response import ExplanationResponse

try:
    from anthropic import Anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class ClaudeProvider(ExplanationProvider):
    def __init__(
        self, model_name: str = "claude-3-5-sonnet-20240620", temperature: float = 0.2
    ):
        super().__init__(model_name, temperature)
        self.client = Anthropic() if self.is_available() else None

    def is_available(self) -> bool:
        return HAS_ANTHROPIC and bool(os.getenv("ANTHROPIC_API_KEY"))

    def generate(self, prompt: PromptPackage) -> ExplanationResponse:
        if not self.is_available() or not self.client:
            raise RuntimeError("Claude provider is not available.")

        start = time.time()

        response = self.client.messages.create(
            model=self.model_name,
            system=prompt.system_prompt,
            messages=[{"role": "user", "content": prompt.user_prompt}],
            temperature=self.temperature,
            max_tokens=2048,
        )

        latency = (time.time() - start) * 1000
        content = response.content[0].text

        return ExplanationResponse(
            generated_text=content,
            provider="claude",
            model=self.model_name,
            latency_ms=latency,
            token_usage={
                "prompt": response.usage.input_tokens,
                "completion": response.usage.output_tokens,
                "total": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
            confidence="high",
        )

    def stream(self, prompt: PromptPackage) -> Generator[str, None, None]:
        if not self.is_available() or not self.client:
            raise RuntimeError("Claude provider is not available.")

        with self.client.messages.stream(
            model=self.model_name,
            system=prompt.system_prompt,
            messages=[{"role": "user", "content": prompt.user_prompt}],
            temperature=self.temperature,
            max_tokens=2048,
        ) as stream:
            yield from stream.text_stream
