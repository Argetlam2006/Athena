"""
backend/explanation/providers/gemini_provider.py — Google Gemini Provider.
"""

from collections.abc import Generator

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.base import ExplanationProvider
from shared.config.settings import settings

try:
    import google.generativeai as genai

    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False


class GeminiProvider(ExplanationProvider):
    def __init__(self, model_name: str | None = None, temperature: float = 0.2):
        # Temporarily set to initializing
        super().__init__("gemini-initializing", temperature)
        if self.is_available():
            genai.configure(api_key=settings.GEMINI_API_KEY)

            supported_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]

            selected_model = None
            # 1. Configured model
            configured_model = model_name or settings.GEMINI_MODEL
            if configured_model:
                for m in supported_models:
                    if m == configured_model or m == f"models/{configured_model}":
                        selected_model = m
                        break

            # 2. Prefer newest Flash model
            if not selected_model:
                flash_models = [m for m in supported_models if "flash" in m.lower() and "lite" not in m.lower() and "preview" not in m.lower() and "image" not in m.lower() and "tts" not in m.lower() and "omni" not in m.lower()]
                if flash_models:
                    versioned = [m for m in flash_models if "latest" not in m.lower()]
                    selected_model = sorted(versioned, reverse=True)[0] if versioned else sorted(flash_models, reverse=True)[0]

            # 3. Prefer newest Pro model
            if not selected_model:
                pro_models = [m for m in supported_models if "pro" in m.lower() and "lite" not in m.lower() and "preview" not in m.lower() and "image" not in m.lower() and "tts" not in m.lower() and "banana" not in m.lower() and "deep-research" not in m.lower()]
                if pro_models:
                    versioned = [m for m in pro_models if "latest" not in m.lower()]
                    selected_model = sorted(versioned, reverse=True)[0] if versioned else sorted(pro_models, reverse=True)[0]

            # 4. Fallback to any flash or pro
            if not selected_model:
                any_flash = [m for m in supported_models if "flash" in m.lower()]
                if any_flash:
                    selected_model = sorted(any_flash, reverse=True)[0]
            if not selected_model:
                any_pro = [m for m in supported_models if "pro" in m.lower()]
                if any_pro:
                    selected_model = sorted(any_pro, reverse=True)[0]

            if not selected_model:
                raise RuntimeError("No compatible Gemini models supporting generateContent were found in the current Google Generative AI SDK.")

            self.model_name = selected_model.replace("models/", "")
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None
            self.model_name = model_name or settings.GEMINI_MODEL

    def is_available(self) -> bool:
        return HAS_GEMINI and bool(settings.GEMINI_API_KEY)


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
