"""
backend/explanation/providers/openai_provider.py — OpenAI Provider.
"""

import os
import time
from collections.abc import Generator

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.base import ExplanationProvider
from backend.explanation.response import ExplanationResponse

try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAIProvider(ExplanationProvider):
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.2):
        super().__init__(model_name, temperature)
        self.client = OpenAI() if self.is_available() else None

    def is_available(self) -> bool:
        return HAS_OPENAI and bool(os.getenv("OPENAI_API_KEY"))

    def _build_messages(self, prompt: PromptPackage) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": prompt.user_prompt},
        ]

    def generate(self, prompt: PromptPackage) -> ExplanationResponse:
        if not self.is_available() or not self.client:
            raise RuntimeError("OpenAI provider is not available.")

        start = time.time()

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self._build_messages(prompt),
            temperature=self.temperature,
        )

        latency = (time.time() - start) * 1000
        content = response.choices[0].message.content or ""

        return ExplanationResponse(
            generated_text=content,
            provider="openai",
            model=self.model_name,
            latency_ms=latency,
            token_usage={
                "prompt": response.usage.prompt_tokens if response.usage else 0,
                "completion": response.usage.completion_tokens if response.usage else 0,
                "total": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
            confidence="high",
        )

    def stream(self, prompt: PromptPackage) -> Generator[str, None, None]:
        if not self.is_available() or not self.client:
            raise RuntimeError("OpenAI provider is not available.")

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self._build_messages(prompt),
            temperature=self.temperature,
            stream=True,
        )

        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
