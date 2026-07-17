import inspect

from backend.explanation.prompt_builder import PromptPackage
from backend.explanation.providers.base import GenerationResponse
from backend.explanation.providers.claude_provider import ClaudeProvider
from backend.explanation.providers.demo_provider import DemoProvider
from backend.explanation.providers.gemini_provider import GeminiProvider
from backend.explanation.providers.openai_provider import OpenAIProvider


def test_demo_provider_returns_generation_response():
    provider = DemoProvider()
    prompt = PromptPackage(
        system_prompt="system",
        user_prompt="user",
        serialized_context="",
        prompt_version="v1",
        metadata={"context_type": "diagnostic"},
    )

    response = provider.generate(prompt)
    assert isinstance(response, GenerationResponse)
    assert isinstance(response.generated_text, str)
    assert response.provider == "demo"
    assert response.model == "athena-demo-model"


def test_demo_provider_stream_yields_generation_response():
    provider = DemoProvider()
    prompt = PromptPackage(
        system_prompt="system",
        user_prompt="user",
        serialized_context="",
        prompt_version="v1",
        metadata={"context_type": "diagnostic"},
    )

    chunks = list(provider.stream(prompt))
    assert len(chunks) > 0
    for chunk in chunks:
        assert isinstance(chunk, GenerationResponse)
        assert isinstance(chunk.generated_text, str)
        assert chunk.provider == "demo"


def test_all_providers_implement_generation_response_signature():
    providers = [DemoProvider, OpenAIProvider, ClaudeProvider, GeminiProvider]

    for provider_cls in providers:
        # Check generate signature
        gen_sig = inspect.signature(provider_cls.generate)
        assert gen_sig.return_annotation == GenerationResponse, (
            f"{provider_cls.__name__}.generate must return GenerationResponse, got {gen_sig.return_annotation}"
        )

        # Check stream signature
        stream_sig = inspect.signature(provider_cls.stream)
        annotation_str = str(stream_sig.return_annotation)
        assert "GenerationResponse" in annotation_str, (
            f"{provider_cls.__name__}.stream must yield GenerationResponse, got {annotation_str}"
        )
        assert "str" not in annotation_str.replace("GenerationResponse", ""), (
            f"{provider_cls.__name__}.stream must not yield str"
        )
