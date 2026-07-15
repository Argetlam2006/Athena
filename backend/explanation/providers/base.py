"""
backend/explanation/providers/base.py — Abstract Provider Interface.
"""

from abc import ABC, abstractmethod
from collections.abc import Generator

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.response import ExplanationResponse


class ExplanationProvider(ABC):
    """
    Abstract base class for all Explanation LLM Providers.
    """

    def __init__(self, model_name: str, temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature

    @abstractmethod
    def generate(self, prompt: PromptPackage) -> ExplanationResponse:
        """
        Synchronously generates a complete explanation.
        """
        pass

    @abstractmethod
    def stream(self, prompt: PromptPackage) -> Generator[str, None, None]:
        """
        Streams the explanation token by token.
        Yields string chunks.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Checks if the provider is properly configured (e.g., API key present).
        """
        pass
