from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.db_models import Episode, Transcript, TranscriptChunk
from app.rag.embeddings import Embedder, EmbeddingError


class RetrievalError(Exception):
    """Raised when semantic retrieval cannot safely produce source results."""


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    episode_id: str
    episode_title: str
    guest_name: str | None
    source_url: str
    text: str
    start_seconds: float | None
    end_seconds: float | None
    topic: str | None
    similarity_score: float


class SemanticRetriever:
    """First-pass pgvector cosine retrieval with an explicit relevance gate."""

    def __init__(self, session: AsyncSession, embedder: Embedder, settings: Settings | None = None) -> None:
        self._session = session
        self._embedder = embedder
        self._settings = settings or get_settings()

    async def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]:
        normalized_query = query.strip()
        if not normalized_query:
            raise RetrievalError("A retrieval query must not be empty.")
        limit = top_k if top_k is not None else self._settings.retrieval_top_k
        if not 1 <= limit <= 100:
            raise RetrievalError("top_k must be between 1 and 100.")

        try:
            vectors = await self._embedder.embed([normalized_query])
        except EmbeddingError:
            raise
        except Exception as error:
            raise RetrievalError("Query embedding failed.") from error
        if len(vectors) != 1 or len(vectors[0]) != self._settings.embedding_dimensions:
            raise RetrievalError("Query embedding has an invalid dimension.")

        cosine_distance = TranscriptChunk.embedding.cosine_distance(vectors[0]).label("cosine_distance")
        statement = (
            select(TranscriptChunk, Episode, cosine_distance)
            .join(Transcript, TranscriptChunk.transcript_id == Transcript.id)
            .join(Episode, Transcript.episode_id == Episode.id)
            .order_by(cosine_distance.asc())
            .limit(limit)
        )
        try:
            rows = (await self._session.execute(statement)).all()
        except Exception as error:
            raise RetrievalError("Vector retrieval failed.") from error

        results = [
            RetrievedChunk(
                chunk_id=str(chunk.id),
                episode_id=str(episode.id),
                episode_title=episode.title,
                guest_name=episode.guest_name,
                source_url=episode.source_url,
                text=chunk.content,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                topic=chunk.topic,
                similarity_score=1.0 - float(distance),
            )
            for chunk, episode, distance in rows
        ]
        return [
            result
            for result in sorted(results, key=lambda item: item.similarity_score, reverse=True)[:limit]
            if result.similarity_score >= self._settings.retrieval_similarity_threshold
        ]
