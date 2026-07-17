"""
backend/explanation/providers/openai_provider.py — OpenAI Provider.
"""

from collections.abc import Generator

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.base import ExplanationProvider, GenerationResponse

try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class OpenAIProvider(ExplanationProvider):
    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.2,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        from shared.config.settings import settings

        def _is_valid(key):
            return bool(key) and "your_" not in key

        # If user didn't specify a model, and we only have an NVIDIA key, default to a free NIM model
        if (
            model_name == "gpt-4o-mini"
            and not _is_valid(settings.OPENAI_API_KEY)
            and _is_valid(settings.NVIDIA_API_KEY)
        ):
            model_name = "meta/llama-3.1-8b-instruct"

        super().__init__(model_name, temperature)
        if not self.is_available():
            self.client = None
            return

        # Default to OpenAI settings (only if OpenAI key is valid)
        final_key = api_key
        if not final_key and _is_valid(settings.OPENAI_API_KEY):
            final_key = settings.OPENAI_API_KEY

        final_url = base_url

        # If user passes an Nvidia model without explicitly providing base URL, automatically use Nvidia's base URL
        if not final_url and (
            self.model_name.startswith("meta/") or self.model_name.startswith("nvidia/")
        ):
            if _is_valid(settings.NVIDIA_API_KEY):
                final_key = settings.NVIDIA_API_KEY
                final_url = "https://integrate.api.nvidia.com/v1"

        self.client = (
            OpenAI(api_key=final_key, base_url=final_url) if HAS_OPENAI else None
        )

    def is_available(self) -> bool:
        from shared.config.settings import settings

        def _is_valid(key):
            return bool(key) and "your_" not in key

        return HAS_OPENAI and (
            _is_valid(settings.OPENAI_API_KEY) or _is_valid(settings.NVIDIA_API_KEY)
        )

    def _build_messages(self, prompt: PromptPackage) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": prompt.system_prompt},
            {"role": "user", "content": prompt.user_prompt},
        ]

    def stream(
        self, prompt: PromptPackage
    ) -> Generator[GenerationResponse, None, None]:
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
                yield GenerationResponse(
                    generated_text=chunk.choices[0].delta.content,
                    provider="openai",
                    model=self.model_name,
                )

    def generate(self, prompt: PromptPackage) -> GenerationResponse:
        if not self.is_available() or not self.client:
            raise RuntimeError("OpenAI provider is not available.")

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=self._build_messages(prompt),
            temperature=self.temperature,
            stream=False,
        )

        choice = response.choices[0]
        usage = dict(response.usage) if response.usage else None

        return GenerationResponse(
            generated_text=choice.message.content,
            provider="openai",
            model=self.model_name,
            finish_reason=choice.finish_reason,
            usage=usage,
        )
