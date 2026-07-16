"""
backend/explanation/providers/claude_provider.py — Anthropic Claude Provider.
"""

import os
from collections.abc import Generator

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.base import ExplanationProvider

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
