"""
backend/explanation/providers/factory.py — Provider Selection Factory.
"""

from backend.explanation.providers.base import ExplanationProvider
from backend.explanation.providers.claude_provider import ClaudeProvider
from backend.explanation.providers.demo_provider import DemoProvider
from backend.explanation.providers.gemini_provider import GeminiProvider
from backend.explanation.providers.openai_provider import OpenAIProvider


def get_provider(provider_config: str = "auto") -> ExplanationProvider:
    """
    Selects and instantiates the appropriate ExplanationProvider.
    Falls back to DemoProvider if the configured provider is unavailable.
    """
    if provider_config == "auto":
        # Priority: Claude -> OpenAI -> Gemini -> Demo
        claude = ClaudeProvider()
        if claude.is_available():
            return claude

        openai = OpenAIProvider()
        if openai.is_available():
            return openai

        gemini = GeminiProvider()
        if gemini.is_available():
            return gemini

        return DemoProvider()

    elif provider_config == "claude":
        claude = ClaudeProvider()
        if claude.is_available():
            return claude
        return DemoProvider()

    elif provider_config == "openai":
        openai = OpenAIProvider()
        if openai.is_available():
            return openai
        return DemoProvider()

    elif provider_config == "gemini":
        gemini = GeminiProvider()
        if gemini.is_available():
            return gemini
        return DemoProvider()

    elif provider_config == "demo":
        return DemoProvider()

    else:
        # Unknown provider fallback
        return DemoProvider()
