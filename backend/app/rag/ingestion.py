import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Episode, Transcript, TranscriptChunk
from app.rag.embeddings import Embedder, EmbeddingError

TOKEN_PATTERN = re.compile(r"[\w'-]+|[^\w\s]", re.UNICODE)
TIMESTAMP_PATTERN = re.compile(r"^\s*\[?(?P<timestamp>(?:\d{1,2}:)?\d{2}:\d{2})\]?\s*")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$")
FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n?", re.DOTALL)
METADATA_KEYS = {"title", "guest", "guest_name", "published_at", "publication_date", "date", "source_url", "url", "external_id", "language", "description"}


class IngestionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class EpisodeMetadata:
    title: str
    guest_name: str | None
    published_at: datetime | None
    source_url: str
    external_id: str | None = None
    language: str = "en"
    description: str | None = None


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    text: str
    start_seconds: float | None
    topic: str | None


@dataclass(frozen=True, slots=True)
class ParsedTranscript:
    metadata: EpisodeMetadata
    raw_text: str
    content_hash: str
    segments: list[TranscriptSegment]


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    id: uuid.UUID
    chunk_index: int
    content: str
    token_count: int
    start_seconds: float | None
    end_seconds: float | None
    topic: str | None


@dataclass(frozen=True, slots=True)
class IngestionResult:
    status: str
    episode_id: uuid.UUID
    transcript_id: uuid.UUID
    chunk_count: int


def _parse_timestamp(value: str) -> float:
    values = [int(part) for part in value.split(":")]
    return float(values[-1] + values[-2] * 60 + (values[-3] * 3600 if len(values) == 3 else 0))


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise IngestionError(f"Invalid publication date: {value!r}.") from error


def _clean(value: str) -> str:
    value = re.sub(r"!?(\[[^\]]*\])\([^)]*\)", r"\1", value)
    value = re.sub(r"[*_`~]", "", value)
    return " ".join(value.split())


def _metadata(values: dict[str, str], path: Path) -> EpisodeMetadata:
    return EpisodeMetadata(
        title=values.get("title") or path.stem.replace("-", " ").replace("_", " ").title(),
        guest_name=values.get("guest") or values.get("guest_name"),
        published_at=_parse_date(values.get("published_at") or values.get("publication_date") or values.get("date")),
        source_url=values.get("source_url") or values.get("url") or path.resolve().as_uri(),
        external_id=values.get("external_id"), language=values.get("language", "en"), description=values.get("description"),
    )


def parse_transcript_file(path: Path) -> ParsedTranscript:
    if path.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise IngestionError("Only Markdown and TXT transcript files are supported.")
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise IngestionError(f"Cannot read transcript file: {path}.") from error
    content, values = raw_text.replace("\r\n", "\n"), {}
    frontmatter = FRONTMATTER_PATTERN.match(content)
    if frontmatter:
        content = content[frontmatter.end():]
        for line in frontmatter.group("body").splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip().lower()] = value.strip().strip('"\'')

    topic, segments = None, []
    for line in content.splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading:
            topic = _clean(heading.group(1))
            values.setdefault("title", topic)
            continue
        if not segments and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            if key in METADATA_KEYS:
                values[key] = value.strip()
                continue
        timestamp = TIMESTAMP_PATTERN.match(line)
        cleaned = _clean(line[timestamp.end():] if timestamp else line)
        if cleaned:
            segments.append(TranscriptSegment(cleaned, _parse_timestamp(timestamp.group("timestamp")) if timestamp else None, topic))
    if not segments:
        raise IngestionError("Transcript contains no ingestible text.")
    normalized = "\n".join(segment.text for segment in segments)
    return ParsedTranscript(_metadata(values, path), raw_text, hashlib.sha256(normalized.encode()).hexdigest(), segments)


def _text(tokens: list[str]) -> str:
    return re.sub(r"\s+([,.;:!?])", r"\1", " ".join(tokens))


def build_chunks(parsed: ParsedTranscript, *, target_tokens: int = 650, overlap_tokens: int = 100) -> list[ChunkDraft]:
    if not 500 <= target_tokens <= 800 or not 0 <= overlap_tokens < target_tokens:
        raise ValueError("Chunk target must be 500–800 with a smaller non-negative overlap.")
    tokens = [(token, segment.start_seconds, segment.topic) for segment in parsed.segments for token in TOKEN_PATTERN.findall(segment.text)]
    chunks, start = [], 0
    while start < len(tokens):
        end = min(start + target_tokens, len(tokens))
        if end < len(tokens):
            for candidate in range(end - 1, start + 499, -1):
                if tokens[candidate][0] in {".", "!", "?"}:
                    end = candidate + 1
                    break
        window = tokens[start:end]
        stamps = [stamp for _, stamp, _ in window if stamp is not None]
        topics = [topic for _, _, topic in window if topic]
        index = len(chunks)
        chunks.append(ChunkDraft(uuid.uuid5(uuid.NAMESPACE_URL, f"{parsed.content_hash}:{index}"), index, _text([token for token, _, _ in window]), len(window), stamps[0] if stamps else None, stamps[-1] if stamps else None, topics[0] if topics else None))
        if end == len(tokens):
            break
        start = max(end - overlap_tokens, start + 1)
    return chunks


class TranscriptIngestionService:
    def __init__(self, session: AsyncSession, embedder: Embedder) -> None:
        self._session, self._embedder = session, embedder

    async def ingest_file(self, path: Path) -> IngestionResult:
        return await self.ingest(parse_transcript_file(path))

    async def ingest(self, parsed: ParsedTranscript) -> IngestionResult:
        chunks = build_chunks(parsed)
        try:
            vectors = await self._embedder.embed([chunk.content for chunk in chunks])
        except EmbeddingError:
            raise
        except Exception as error:
            raise EmbeddingError("Embedding generation failed.") from error
        if len(vectors) != len(chunks) or any(len(vector) != self._embedder.dimensions for vector in vectors):
            raise EmbeddingError("Embedding count or dimensions are invalid.")
        async with self._session.begin():
            episode = await self._session.scalar(select(Episode).where(Episode.source_url == parsed.metadata.source_url))
            if episode is None:
                episode = Episode(source_url=parsed.metadata.source_url, title=parsed.metadata.title)
                self._session.add(episode)
                await self._session.flush()
            episode.title, episode.guest_name, episode.published_at = parsed.metadata.title, parsed.metadata.guest_name, parsed.metadata.published_at
            episode.external_id, episode.description = parsed.metadata.external_id, parsed.metadata.description
            transcript = await self._session.scalar(select(Transcript).where(Transcript.episode_id == episode.id))
            if transcript is not None and transcript.content_hash == parsed.content_hash:
                return IngestionResult("skipped", episode.id, transcript.id, 0)
            status = "created" if transcript is None else "updated"
            if transcript is None:
                transcript = Transcript(episode_id=episode.id, source_url=parsed.metadata.source_url, content_hash=parsed.content_hash, raw_text=parsed.raw_text, language=parsed.metadata.language, ingest_metadata={"source_url": parsed.metadata.source_url})
                self._session.add(transcript)
                await self._session.flush()
            else:
                await self._session.execute(delete(TranscriptChunk).where(TranscriptChunk.transcript_id == transcript.id))
                transcript.content_hash, transcript.raw_text, transcript.language = parsed.content_hash, parsed.raw_text, parsed.metadata.language
                transcript.ingest_metadata = {"source_url": parsed.metadata.source_url}
            self._session.add_all([TranscriptChunk(id=chunk.id, transcript_id=transcript.id, chunk_index=chunk.chunk_index, content=chunk.content, token_count=chunk.token_count, start_seconds=chunk.start_seconds, end_seconds=chunk.end_seconds, topic=chunk.topic, chunk_metadata={"content_hash": parsed.content_hash}, embedding=vector) for chunk, vector in zip(chunks, vectors, strict=True)])
        return IngestionResult(status, episode.id, transcript.id, len(chunks))
