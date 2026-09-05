import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.providers.base import BaseLLMProvider, LLMRequest, ProviderError
from app.rag.embeddings import EmbeddingError
from app.rag.retriever import RetrievedChunk, RetrievalError

INSUFFICIENT_EVIDENCE_MESSAGE = "I do not have sufficient information in Lenny's podcast archive to answer this."
SOURCE_LABEL_PATTERN = re.compile(r"\[S(?P<index>\d+)\]")


class RAGError(Exception):
    """Raised when grounded answer generation fails after retrieval."""


class RetrievalPort(Protocol):
    async def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]: ...


class SourceCitation(BaseModel):
    source_id: str
    episode: str
    guest: str | None
    timestamp: str | None
    topic: str | None
    source_url: str
    similarity_score: float


class RetrievalMetadata(BaseModel):
    retrieved_count: int
    used_source_count: int
    threshold: float
    top_similarity_score: float | None
    provider: str | None = None
    model: str | None = None


class GroundedResponse(BaseModel):
    answer: str
    sources: list[SourceCitation] = Field(default_factory=list)
    retrieval_metadata: RetrievalMetadata


@dataclass(frozen=True, slots=True)
class ContextBuild:
    prompt_context: str
    sources: list[SourceCitation]


@dataclass(frozen=True, slots=True)
class GroundedStreamEvent:
    event: str
    data: object


def format_timestamp(seconds: float | None) -> str | None:
    if seconds is None or seconds < 0:
        return None
    total_seconds = round(seconds)
    hours, remainder = divmod(total_seconds, 3_600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def format_citation(source: SourceCitation) -> str:
    details = [f"Episode: {source.episode}"]
    if source.guest:
        details.append(f"Guest: {source.guest}")
    if source.timestamp:
        details.append(f"Timestamp: {source.timestamp}")
    if source.topic:
        details.append(f"Topic: {source.topic}")
    return " — ".join(details)


def _is_valid_chunk(chunk: RetrievedChunk) -> bool:
    return bool(chunk.chunk_id and chunk.episode_title.strip() and chunk.source_url.strip() and chunk.text.strip())


def build_context(chunks: list[RetrievedChunk]) -> ContextBuild:
    sources: list[SourceCitation] = []
    entries: list[str] = []
    for chunk in chunks:
        if not _is_valid_chunk(chunk):
            continue
        source = SourceCitation(
            source_id=f"S{len(sources) + 1}",
            episode=chunk.episode_title,
            guest=chunk.guest_name,
            timestamp=format_timestamp(chunk.start_seconds),
            topic=chunk.topic,
            source_url=chunk.source_url,
            similarity_score=chunk.similarity_score,
        )
        sources.append(source)
        entries.append(f"[{source.source_id}] {format_citation(source)}\nExcerpt: {chunk.text}")
    return ContextBuild(prompt_context="\n\n".join(entries), sources=sources)


def build_system_prompt() -> str:
    return (
        "You answer questions only from the supplied Lenny's Podcast transcript excerpts. "
        "Do not use outside knowledge or invent guests, episodes, timestamps, quotes, strategies, or statistics. "
        "If the excerpts do not support an answer, state that the archive has insufficient information. "
        "For each substantive claim, cite one or more supplied source labels exactly as [S1], [S2], and so on."
    )


def validate_generated_answer(answer: str, source_count: int) -> str:
    normalized = answer.strip()
    if not normalized:
        raise RAGError("The language model returned an empty answer.")
    labels = [match.group("index") for match in SOURCE_LABEL_PATTERN.finditer(normalized)]
    if not labels:
        raise RAGError("The language model returned an answer without source citations.")
    invalid_labels = [label for label in labels if not 1 <= int(label) <= source_count]
    if invalid_labels:
        raise RAGError("The language model referenced a source that was not retrieved.")
    return normalized


class GroundedRAGEngine:
    def __init__(self, retriever: RetrievalPort, provider: BaseLLMProvider, settings: Settings | None = None) -> None:
        self._retriever = retriever
        self._provider = provider
        self._settings = settings or get_settings()

    async def answer(self, query: str) -> GroundedResponse:
        try:
            chunks = await self._retriever.retrieve(query, top_k=self._settings.retrieval_top_k)
        except (RetrievalError, EmbeddingError) as error:
            raise RAGError("Grounded retrieval failed.") from error
        context = build_context(chunks)
        top_score = max((chunk.similarity_score for chunk in chunks), default=None)
        base_metadata = {
            "retrieved_count": len(chunks),
            "used_source_count": len(context.sources),
            "threshold": self._settings.retrieval_similarity_threshold,
            "top_similarity_score": top_score,
        }
        if not context.sources:
            return GroundedResponse(
                answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                sources=[],
                retrieval_metadata=RetrievalMetadata(**base_metadata),
            )
        try:
            generation = await self._provider.generate(
                LLMRequest(
                    system_prompt=build_system_prompt(),
                    user_prompt=f"Question: {query.strip()}\n\nTranscript evidence:\n{context.prompt_context}",
                    temperature=self._settings.rag_temperature,
                    max_output_tokens=self._settings.rag_max_output_tokens,
                )
            )
        except ProviderError as error:
            raise RAGError("Grounded answer generation failed.") from error
        answer = validate_generated_answer(generation.text, len(context.sources))
        return GroundedResponse(
            answer=answer,
            sources=context.sources,
            retrieval_metadata=RetrievalMetadata(**base_metadata, provider=generation.provider, model=generation.model),
        )

    async def stream(self, query: str) -> AsyncIterator[GroundedStreamEvent]:
        try:
            chunks = await self._retriever.retrieve(query, top_k=self._settings.retrieval_top_k)
        except (RetrievalError, EmbeddingError) as error:
            raise RAGError("Grounded retrieval failed.") from error
        context = build_context(chunks)
        base_metadata = {"retrieved_count": len(chunks), "used_source_count": len(context.sources), "threshold": self._settings.retrieval_similarity_threshold, "top_similarity_score": max((chunk.similarity_score for chunk in chunks), default=None)}
        if not context.sources:
            response = GroundedResponse(answer=INSUFFICIENT_EVIDENCE_MESSAGE, sources=[], retrieval_metadata=RetrievalMetadata(**base_metadata))
            yield GroundedStreamEvent("token", {"text": response.answer})
            yield GroundedStreamEvent("done", response)
            return
        for source in context.sources:
            yield GroundedStreamEvent("source", source)
        request = LLMRequest(system_prompt=build_system_prompt(), user_prompt=f"Question: {query.strip()}\n\nTranscript evidence:\n{context.prompt_context}", temperature=self._settings.rag_temperature, max_output_tokens=self._settings.rag_max_output_tokens)
        chunks_out: list[str] = []
        try:
            async for delta in self._provider.stream(request):
                chunks_out.append(delta)
                yield GroundedStreamEvent("token", {"text": delta})
        except ProviderError as error:
            raise RAGError("Grounded answer generation failed.") from error
        answer = validate_generated_answer("".join(chunks_out), len(context.sources))
        response = GroundedResponse(answer=answer, sources=context.sources, retrieval_metadata=RetrievalMetadata(**base_metadata, provider=self._provider.name, model=request.model))
        yield GroundedStreamEvent("done", response)
