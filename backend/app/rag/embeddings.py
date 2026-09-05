import asyncio
import logging
from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Raised when an embedding model cannot produce valid vectors."""


class Embedder(ABC):
    dimensions: int

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding per non-empty input text."""


class SentenceTransformerEmbedder(Embedder):
    """Local embedding adapter; inference stays off the event loop."""

    def __init__(self, model_name: str, dimensions: int) -> None:
        self.dimensions = dimensions
        self._model_name = model_name
        self._model = None

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logging.getLogger(__name__).info("embedding_model_loading", extra={"model": self._model_name})
            self._model = SentenceTransformer(self._model_name)
            logging.getLogger(__name__).info("embedding_model_loaded", extra={"model": self._model_name, "dimensions": self.dimensions})
        return self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingError("Embedding inputs must be non-empty.")
        vectors = await asyncio.to_thread(self._embed_sync, texts)
        if len(vectors) != len(texts) or any(len(vector) != self.dimensions for vector in vectors):
            raise EmbeddingError(f"Embedding model must return {self.dimensions}-dimension vectors.")
        return vectors
