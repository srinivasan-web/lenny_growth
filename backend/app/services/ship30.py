import re
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, get_settings
from app.providers.base import BaseLLMProvider, LLMRequest, ProviderError
from app.rag.grounded import SourceCitation, build_context, format_citation
from app.rag.retriever import RetrievedChunk


class Ship30Error(Exception):
    """Raised when Ship 30 content cannot be safely produced."""


class Ship30ValidationError(Ship30Error):
    """Raised when evidence or generated Markdown fails content checks."""


class Ship30GenerationError(Ship30Error):
    """Raised when the language model cannot generate the artifact."""


class TranscriptRetriever(Protocol):
    async def retrieve(self, query: str, *, top_k: int | None = None) -> list[RetrievedChunk]: ...


@dataclass(frozen=True, slots=True)
class Ship30Artifact:
    markdown: str
    word_count: int
    sources: list[SourceCitation]
    provider: str
    model: str


WORD_COUNT_TARGET = 1_250
MIN_WORD_COUNT = 1_000
MAX_WORD_COUNT = 1_500
SOURCE_LABEL_PATTERN = re.compile(r"\[S(?P<index>\d+)\]")
GUEST_CLAIM_PATTERN = re.compile(
    r"\b(?:guest|interviewee)\s+(?:is|was|named|called)\s+(?P<name>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*)"
)


def count_words(markdown: str) -> int:
    return len(re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", markdown))


def build_ship30_system_prompt() -> str:
    return (
        "You are the Ship 30 for 30 content engine for Lenny's Podcast. "
        "Write one practical essay of approximately 1,250 words in Markdown using only the supplied transcript evidence. "
        "Do not use outside knowledge, invent guests, or attribute a claim to a guest unless the evidence supports it. "
        "Every substantive claim must cite supplied source labels exactly as [S1], [S2], and so on. "
        "Use this exact editorial shape: a strong H1 headline; an opening curiosity and outcome hook; short paragraphs; "
        "at least two H2 sections and one H3 subsection; bold anchors; bullets; a checklist or named framework; "
        "an actionable conclusion; and a final H2 section titled Sources with source labels and episode details. "
        "Do not add a preface outside the essay."
    )


def _source_labels(markdown: str) -> list[str]:
    return [match.group("index") for match in SOURCE_LABEL_PATTERN.finditer(markdown)]


def validate_ship30_markdown(markdown: str, sources: list[SourceCitation]) -> str:
    normalized = markdown.strip()
    if not normalized:
        raise Ship30ValidationError("The generated Ship 30 artifact is empty.")

    word_count = count_words(normalized)
    if not MIN_WORD_COUNT <= word_count <= MAX_WORD_COUNT:
        raise Ship30ValidationError(
            f"The generated artifact has {word_count} words; expected approximately {WORD_COUNT_TARGET}."
        )
    if not re.search(r"^#\s+\S", normalized, re.MULTILINE):
        raise Ship30ValidationError("The artifact must contain a strong H1 headline.")
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    if len(paragraphs) < 2 or not re.search(r"\?|curious|surprising|outcome|result", paragraphs[1], re.IGNORECASE):
        raise Ship30ValidationError("The artifact must open with a curiosity or outcome hook.")
    if len(re.findall(r"^##\s+\S", normalized, re.MULTILINE)) < 2:
        raise Ship30ValidationError("The artifact must contain at least two H2 sections.")
    if not re.search(r"^###\s+\S", normalized, re.MULTILINE):
        raise Ship30ValidationError("The artifact must contain an H3 subsection.")
    if not re.search(r"\*\*[^*]+\*\*", normalized):
        raise Ship30ValidationError("The artifact must contain bold anchors.")
    if not re.search(r"^\s*(?:[-*]|\d+\.)\s+\S", normalized, re.MULTILINE):
        raise Ship30ValidationError("The artifact must contain bullets or a checklist.")
    if not re.search(r"checklist|framework", normalized, re.IGNORECASE):
        raise Ship30ValidationError("The artifact must contain a checklist or framework.")
    if not re.search(r"^##\s+(?:.*\b(?:conclusion|next steps|action)\b).*$", normalized, re.MULTILINE | re.IGNORECASE):
        raise Ship30ValidationError("The artifact must contain an actionable conclusion.")
    if not re.search(r"^##\s+Sources\s*$", normalized, re.MULTILINE | re.IGNORECASE):
        raise Ship30ValidationError("The artifact must contain a Sources section.")

    labels = _source_labels(normalized)
    if not labels:
        raise Ship30ValidationError("The artifact must attribute claims to transcript sources.")
    invalid_labels = [label for label in labels if not 1 <= int(label) <= len(sources)]
    if invalid_labels:
        raise Ship30ValidationError("The artifact references a source that was not retrieved.")

    known_guests = {source.guest.casefold() for source in sources if source.guest}
    for match in GUEST_CLAIM_PATTERN.finditer(normalized):
        if match.group("name").casefold() not in known_guests:
            raise Ship30ValidationError("The artifact contains an unsupported guest attribution.")
    return normalized


class Ship30ContentService:
    def __init__(
        self,
        retriever: TranscriptRetriever,
        provider: BaseLLMProvider,
        settings: Settings | None = None,
    ) -> None:
        self._retriever = retriever
        self._provider = provider
        self._settings = settings or get_settings()

    async def generate(self, topic: str) -> Ship30Artifact:
        normalized_topic = topic.strip()
        if not normalized_topic:
            raise Ship30ValidationError("A topic is required.")
        chunks = await self._retriever.retrieve(normalized_topic, top_k=self._settings.retrieval_top_k)
        context = build_context(chunks)
        if not context.sources or not context.prompt_context.strip():
            raise Ship30ValidationError("No transcript evidence was retrieved for this topic.")

        request = LLMRequest(
            system_prompt=build_ship30_system_prompt(),
            user_prompt=(
                f"Topic: {normalized_topic}\n\n"
                f"Transcript evidence:\n{context.prompt_context}\n\n"
                "Write the complete Ship 30 essay now."
            ),
            temperature=self._settings.rag_temperature,
            max_output_tokens=self._settings.ship30_max_output_tokens,
        )
        try:
            generation = await self._provider.generate(request)
        except ProviderError as error:
            raise Ship30GenerationError("Ship 30 content generation failed.") from error

        markdown = validate_ship30_markdown(generation.text, context.sources)
        return Ship30Artifact(
            markdown=markdown,
            word_count=count_words(markdown),
            sources=context.sources,
            provider=generation.provider,
            model=generation.model,
        )