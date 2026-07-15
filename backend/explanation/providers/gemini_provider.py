"""
backend/explanation/providers/gemini_provider.py — Google Gemini Provider.
"""

import os
import time
from collections.abc import Generator

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.base import ExplanationProvider
from backend.explanation.response import ExplanationResponse

try:
    import google.generativeai as genai

    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


class GeminiProvider(ExplanationProvider):
    def __init__(self, model_name: str = "gemini-1.5-flash", temperature: float = 0.2):
        super().__init__(model_name, temperature)
        if self.is_available():
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None

    def is_available(self) -> bool:
        return HAS_GEMINI and bool(os.getenv("GEMINI_API_KEY"))

    def generate(self, prompt: PromptPackage) -> ExplanationResponse:
        if not self.is_available() or not self.model:
            raise RuntimeError("Gemini provider is not available.")

        start = time.time()

        # Combine system and user for Gemini (or use GenerationConfig)
        full_prompt = f"{prompt.system_prompt}\n\n{prompt.user_prompt}"

        response = self.model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=self.temperature
            ),
        )

        latency = (time.time() - start) * 1000
        content = response.text

        return ExplanationResponse(
            generated_text=content,
            provider="gemini",
            model=self.model_name,
            latency_ms=latency,
            token_usage={
                "prompt": 0,
                "completion": 0,
                "total": 0,
            },  # Note: Gemini SDK doesn't natively expose tokens in this basic way without extra calls
            finish_reason="stop",
            confidence="high",
        )

    def stream(self, prompt: PromptPackage) -> Generator[str, None, None]:
        if not self.is_available() or not self.model:
            raise RuntimeError("Gemini provider is not available.")

        full_prompt = f"{prompt.system_prompt}\n\n{prompt.user_prompt}"

        response = self.model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=self.temperature
            ),
            stream=True,
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text
