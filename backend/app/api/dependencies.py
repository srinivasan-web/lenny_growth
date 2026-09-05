from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db_session
from app.providers.factory import get_llm_provider
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.grounded import GroundedRAGEngine
from app.rag.retriever import SemanticRetriever
from app.services.chat import ChatService
from app.services.health import HealthService
from app.services.sessions import SessionService
from app.services.ship30 import Ship30ContentService


@lru_cache
def get_embedder() -> SentenceTransformerEmbedder:
    settings = get_settings()
    return SentenceTransformerEmbedder(settings.embedding_model, settings.embedding_dimensions)


def get_session_service(db: AsyncSession = Depends(get_db_session)) -> SessionService:
    return SessionService(db)


def get_health_service(db: AsyncSession = Depends(get_db_session)) -> HealthService:
    return HealthService(db, get_settings())


def build_chat_service(db: AsyncSession, provider: str | None = None) -> ChatService:
    settings = get_settings()
    if provider:
        settings = settings.model_copy(update={"default_llm_provider": provider})
    rag = GroundedRAGEngine(SemanticRetriever(db, get_embedder(), settings), get_llm_provider(settings), settings)
    return ChatService(db, rag)


def get_chat_service(db: AsyncSession = Depends(get_db_session)) -> ChatService:
    return build_chat_service(db)


def get_chat_service_factory(db: AsyncSession = Depends(get_db_session)) -> Callable[[str | None], ChatService]:
    return lambda provider=None: build_chat_service(db, provider)


def build_ship30_service(db: AsyncSession, provider: str | None = None) -> Ship30ContentService:
    settings = get_settings()
    if provider:
        settings = settings.model_copy(update={"default_llm_provider": provider})
    retriever = SemanticRetriever(db, get_embedder(), settings)
    return Ship30ContentService(retriever, get_llm_provider(settings), settings)


def get_ship30_service_factory(db: AsyncSession = Depends(get_db_session)) -> Callable[[str | None], Ship30ContentService]:
    return lambda provider=None: build_ship30_service(db, provider)
