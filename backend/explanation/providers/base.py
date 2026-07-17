"""
backend/explanation/providers/base.py — Abstract Provider Interface.
"""

from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass

from backend.explanation.prompt_builder import PromptPackage

@dataclass
class GenerationResponse:
    generated_text: str
    provider: str
    model: str
    finish_reason: str | None = None
    usage: dict | None = None


class ExplanationProvider(ABC):
    """
    Abstract base class for all Explanation LLM Providers.
    """

    def __init__(self, model_name: str, temperature: float = 0.2):
        self.model_name = model_name
        self.temperature = temperature


    @abstractmethod
    def stream(self, prompt: PromptPackage) -> Generator[GenerationResponse, None, None]:
        """
        Streams the explanation token by token.
        Yields GenerationResponse objects containing the chunk text in `generated_text`.
        """
        pass

    @abstractmethod
    def generate(self, prompt: PromptPackage) -> GenerationResponse:
        """
        Generates the explanation as a single complete response.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Checks if the provider is properly configured (e.g., API key present).
        """
        pass
