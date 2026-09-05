from collections.abc import AsyncIterator

import pytest

from app.config import Settings
from app.providers.base import LLMGeneration, LLMProvider, LLMRequest, ProviderError
from app.rag.grounded import SourceCitation
from app.rag.retriever import RetrievedChunk
from app.services.ship30 import (
    Ship30ContentService,
    Ship30GenerationError,
    Ship30ValidationError,
    validate_ship30_markdown,
)


class StubRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks

    async def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        return self.chunks


class StubProvider(LLMProvider):
    name = "stub"

    def __init__(self, text: str) -> None:
        self.text = text
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMGeneration:
        self.requests.append(request)
        return LLMGeneration(text=self.text, provider=self.name, model="stub-model")

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        yield self.text


class FailingProvider(StubProvider):
    async def generate(self, request: LLMRequest) -> LLMGeneration:
        raise ProviderError("unavailable")


def settings() -> Settings:
    return Settings(database_url="postgresql+asyncpg://test:test@localhost/test")


def source() -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="chunk-1",
        episode_id="episode-1",
        episode_title="Activation Principles",
        guest_name="Ada Example",
        source_url="https://example.com/episode-1",
        text="Users should reach a first success quickly.",
        start_seconds=90.0,
        end_seconds=120.0,
        topic="Activation",
        similarity_score=0.92,
    )


def valid_markdown() -> str:
    body = " ".join("The first successful action should be designed deliberately [S1]." for _ in range(130))
    return f"""# The First Win Is the Growth Strategy

The surprising lever is the first successful action. This essay shows how to turn that moment into a repeatable outcome [S1].

## Start With the First Win

**Find the moment that matters.** {body}

### A Practical Checklist

- Define the first successful action [S1].
- Remove friction before that action [S1].
- Measure whether users reach it [S1].

## Make the Lesson Repeatable

**Build the loop.** {body}

## Conclusion: Run the Next Experiment

Choose one activation moment, remove one obstacle, and measure the result this week [S1].

## Sources

- [S1] Episode: Activation Principles - Guest: Ada Example | https://example.com/episode-1
"""


def citations() -> list[SourceCitation]:
    return [
        SourceCitation(
            source_id="S1",
            episode="Activation Principles",
            guest="Ada Example",
            timestamp="01:30",
            topic="Activation",
            source_url="https://example.com/episode-1",
            similarity_score=0.92,
        )
    ]


@pytest.mark.asyncio
async def test_ship30_pipeline_returns_valid_markdown_artifact() -> None:
    provider = StubProvider(valid_markdown())
    artifact = await Ship30ContentService(StubRetriever([source()]), provider, settings()).generate("activation")

    assert 1_000 <= artifact.word_count <= 1_500
    assert artifact.markdown.startswith("# The First Win")
    assert provider.requests[0].max_output_tokens == 2400
    assert "Activation Principles" in provider.requests[0].user_prompt


@pytest.mark.asyncio
async def test_empty_context_is_rejected_without_generation() -> None:
    provider = StubProvider(valid_markdown())

    with pytest.raises(Ship30ValidationError, match="No transcript evidence"):
        await Ship30ContentService(StubRetriever([]), provider, settings()).generate("activation")

    assert provider.requests == []


@pytest.mark.asyncio
async def test_provider_failure_is_reported() -> None:
    with pytest.raises(Ship30GenerationError, match="generation failed"):
        await Ship30ContentService(StubRetriever([source()]), FailingProvider(valid_markdown()), settings()).generate("activation")


@pytest.mark.parametrize(
    ("markdown", "message"),
    [
        ("# Short\n\nNo supporting evidence.", "approximately"),
        (" ".join(["word"] * 1_200), "strong H1"),
        (valid_markdown().replace("## Sources", "## References"), "Sources section"),
        (valid_markdown().replace("[S1]", "[S9]"), "not retrieved"),
    ],
)
def test_ship30_validation_rejects_invalid_artifacts(markdown: str, message: str) -> None:
    with pytest.raises(Ship30ValidationError, match=message):
        validate_ship30_markdown(markdown, citations())


def test_ship30_validation_rejects_unsupported_guest_claim() -> None:
    markdown = valid_markdown().replace("The surprising lever", "The guest is Unknown Person. The surprising lever", 1)

    with pytest.raises(Ship30ValidationError, match="unsupported guest"):
        validate_ship30_markdown(markdown, citations())