from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.rag.embeddings import Embedder
from app.rag.retriever import RetrievalError, SemanticRetriever


class StubEmbedder(Embedder):
    dimensions = 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self.dimensions for _ in texts]


class StubResult:
    def __init__(self, rows: list[tuple[object, object, float]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[object, object, float]]:
        return self._rows


class StubSession:
    def __init__(self, rows: list[tuple[object, object, float]]) -> None:
        self._rows = rows

    async def execute(self, statement: object) -> StubResult:
        return StubResult(self._rows)


def settings(**overrides: object) -> Settings:
    return Settings(database_url="postgresql+asyncpg://test:test@localhost/test", retrieval_top_k=5, retrieval_similarity_threshold=0.35, **overrides)


def row(identifier: str, distance: float) -> tuple[object, object, float]:
    chunk = SimpleNamespace(id=f"chunk-{identifier}", content=f"text-{identifier}", start_seconds=12.0, end_seconds=18.0, topic="Activation")
    episode = SimpleNamespace(id=f"episode-{identifier}", title=f"Episode {identifier}", guest_name="Guest", source_url=f"https://example.com/{identifier}")
    return chunk, episode, distance


@pytest.mark.asyncio
async def test_relevant_query_returns_cited_result() -> None:
    results = await SemanticRetriever(StubSession([row("relevant", 0.1)]), StubEmbedder(), settings()).retrieve("activation strategy")

    assert len(results) == 1
    assert results[0].episode_title == "Episode relevant"
    assert results[0].similarity_score == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_irrelevant_query_returns_no_results_below_threshold() -> None:
    results = await SemanticRetriever(StubSession([row("irrelevant", 0.8)]), StubEmbedder(), settings()).retrieve("unrelated question")

    assert results == []


@pytest.mark.asyncio
async def test_empty_database_returns_no_results() -> None:
    results = await SemanticRetriever(StubSession([]), StubEmbedder(), settings()).retrieve("activation")

    assert results == []


@pytest.mark.asyncio
async def test_low_similarity_is_filtered() -> None:
    results = await SemanticRetriever(StubSession([row("low", 0.66)]), StubEmbedder(), settings()).retrieve("activation")

    assert results == []


@pytest.mark.asyncio
async def test_top_k_results_are_sorted_by_similarity() -> None:
    rows = [row("third", 0.3), row("first", 0.05), row("second", 0.2)]
    results = await SemanticRetriever(StubSession(rows), StubEmbedder(), settings()).retrieve("activation", top_k=2)

    assert [result.episode_title for result in results] == ["Episode first", "Episode second"]


@pytest.mark.asyncio
async def test_empty_query_is_rejected() -> None:
    with pytest.raises(RetrievalError, match="must not be empty"):
        await SemanticRetriever(StubSession([]), StubEmbedder(), settings()).retrieve("  ")
