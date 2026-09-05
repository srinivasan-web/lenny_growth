from collections.abc import AsyncIterator

import pytest

from app.config import Settings
from app.providers.base import LLMGeneration, LLMProvider, LLMRequest, ProviderError
from app.rag.grounded import GroundedRAGEngine, INSUFFICIENT_EVIDENCE_MESSAGE, RAGError, format_citation
from app.rag.retriever import RetrievedChunk


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    async def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        return self._chunks


class StubProvider(LLMProvider):
    name = "stub"

    def __init__(self, text: str = "Activation should focus on the first successful user action [S1].") -> None:
        self.text = text
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMGeneration:
        self.requests.append(request)
        return LLMGeneration(text=self.text, provider=self.name, model="stub-model")

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        yield self.text


class FailingProvider(StubProvider):
    async def generate(self, request: LLMRequest) -> LLMGeneration:
        raise ProviderError("network unavailable")


def settings() -> Settings:
    return Settings(database_url="postgresql+asyncpg://test:test@localhost/test", retrieval_similarity_threshold=0.35)


def source(**overrides: object) -> RetrievedChunk:
    values: dict[str, object] = {
        "chunk_id": "chunk-1",
        "episode_id": "episode-1",
        "episode_title": "Activation Principles",
        "guest_name": "Ada Example",
        "source_url": "https://example.com/episode-1",
        "text": "Users should reach a first success quickly.",
        "start_seconds": 90.0,
        "end_seconds": 120.0,
        "topic": "Activation",
        "similarity_score": 0.92,
    }
    values.update(overrides)
    return RetrievedChunk(**values)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_grounded_answer_uses_retrieved_context() -> None:
    provider = StubProvider()
    result = await GroundedRAGEngine(StubRetriever([source()]), provider, settings()).answer("How should I improve activation?")

    assert result.answer.endswith("[S1].")
    assert result.retrieval_metadata.provider == "stub"
    assert "Activation Principles" in provider.requests[0].user_prompt
    assert "Users should reach a first success quickly." in provider.requests[0].user_prompt


@pytest.mark.asyncio
async def test_no_relevant_context_returns_required_refusal_without_provider_call() -> None:
    provider = StubProvider()
    result = await GroundedRAGEngine(StubRetriever([]), provider, settings()).answer("What is the weather?")

    assert result.answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert result.sources == []
    assert provider.requests == []


@pytest.mark.asyncio
async def test_response_contains_programmatic_citation_details() -> None:
    result = await GroundedRAGEngine(StubRetriever([source()]), StubProvider(), settings()).answer("How should I improve activation?")

    citation = result.sources[0]
    assert citation.episode == "Activation Principles"
    assert citation.guest == "Ada Example"
    assert citation.timestamp == "01:30"
    assert citation.topic == "Activation"
    assert "Episode: Activation Principles" in format_citation(citation)


@pytest.mark.asyncio
async def test_malformed_context_is_treated_as_insufficient_evidence() -> None:
    malformed = source(text="", episode_title="")
    provider = StubProvider()
    result = await GroundedRAGEngine(StubRetriever([malformed]), provider, settings()).answer("Activation?")

    assert result.answer == INSUFFICIENT_EVIDENCE_MESSAGE
    assert provider.requests == []


@pytest.mark.asyncio
async def test_provider_failure_is_reported_not_fabricated() -> None:
    with pytest.raises(RAGError, match="Grounded answer generation failed"):
        await GroundedRAGEngine(StubRetriever([source()]), FailingProvider(), settings()).answer("Activation?")


@pytest.mark.asyncio
async def test_answer_without_citation_is_rejected() -> None:
    with pytest.raises(RAGError, match="without source citations"):
        await GroundedRAGEngine(StubRetriever([source()]), StubProvider("Use a first success moment."), settings()).answer("Activation?")
