from types import SimpleNamespace

import pytest

from app.config import Settings
from app.providers.base import BaseLLMProvider, LLMRequest, ProviderError
from app.providers.cloud_provider import CloudProvider
from app.providers.factory import get_llm_provider
from app.providers.ollama_provider import OllamaProvider


def make_settings(**overrides: object) -> Settings:
    return Settings(database_url="postgresql+asyncpg://test:test@localhost/test", **overrides)


def test_factory_creates_cloud_provider_without_exposing_key() -> None:
    provider = get_llm_provider(make_settings(default_llm_provider="cloud", openai_api_key="test-key"))

    assert isinstance(provider, CloudProvider)


def test_factory_creates_ollama_provider() -> None:
    provider = get_llm_provider(make_settings(default_llm_provider="ollama"))

    assert isinstance(provider, OllamaProvider)


def test_provider_switching_preserves_the_same_base_interface() -> None:
    ollama = get_llm_provider(make_settings(default_llm_provider="ollama"))
    cloud = get_llm_provider(make_settings(default_llm_provider="cloud", openai_api_key="test-key"))

    assert isinstance(ollama, BaseLLMProvider)
    assert isinstance(cloud, BaseLLMProvider)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ProviderError, match="Unsupported LLM provider"):
        get_llm_provider(make_settings(default_llm_provider="unknown"))


@pytest.mark.asyncio
async def test_cloud_provider_normalizes_provider_failure() -> None:
    provider = CloudProvider(api_key="test-key", default_model="test-model", timeout_seconds=1)

    class FailingResponses:
        async def create(self, **kwargs: object) -> object:
            raise Exception("upstream failure")

    provider._client = SimpleNamespace(responses=FailingResponses())  # type: ignore[attr-defined]
    with pytest.raises(ProviderError, match="OpenAI generation failed"):
        await provider.generate(LLMRequest(system_prompt="system", user_prompt="user"))


@pytest.mark.asyncio
async def test_cloud_provider_exposes_async_streaming_interface() -> None:
    provider = CloudProvider(api_key="test-key", default_model="test-model", timeout_seconds=1)

    class Stream:
        def __init__(self) -> None:
            self._events = iter([
                SimpleNamespace(type="response.output_text.delta", delta="hello "),
                SimpleNamespace(type="response.output_text.delta", delta="world"),
            ])

        def __aiter__(self) -> "Stream":
            return self

        async def __anext__(self) -> object:
            try:
                return next(self._events)
            except StopIteration as error:
                raise StopAsyncIteration from error

    class StreamingResponses:
        async def create(self, **kwargs: object) -> Stream:
            assert kwargs["stream"] is True
            return Stream()

    provider._client = SimpleNamespace(responses=StreamingResponses())  # type: ignore[attr-defined]
    deltas = [delta async for delta in provider.stream(LLMRequest(system_prompt="system", user_prompt="user"))]

    assert deltas == ["hello ", "world"]
