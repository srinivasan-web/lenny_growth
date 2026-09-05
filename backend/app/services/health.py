import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models.schemas import DependencyStatus, HealthResponse


class HealthService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db, self._settings = db, settings

    async def check(self) -> HealthResponse:
        database = await self._database_status()
        vector_index = await self._vector_status() if database.status == "ok" else DependencyStatus(status="unavailable", detail="database unavailable")
        ollama = await self._ollama_status() if self._settings.default_llm_provider.lower() == "ollama" else DependencyStatus(status="not_configured", detail="Ollama is not the active provider")
        required_statuses = [database.status, vector_index.status]
        if self._settings.default_llm_provider.lower() == "ollama":
            required_statuses.append(ollama.status)
        statuses = required_statuses
        status = "ok" if all(item == "ok" for item in statuses) else "degraded"
        return HealthResponse(status=status, database=database, ollama=ollama, vector_index=vector_index)

    async def _database_status(self) -> DependencyStatus:
        try:
            await self._db.execute(text("SELECT 1"))
            return DependencyStatus(status="ok")
        except Exception:
            return DependencyStatus(status="unavailable", detail="database query failed")

    async def _vector_status(self) -> DependencyStatus:
        try:
            extension = await self._db.scalar(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            index = await self._db.scalar(text("SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'ix_transcript_chunks_embedding_hnsw'"))
            if extension and index:
                return DependencyStatus(status="ok")
            return DependencyStatus(status="unavailable", detail="pgvector extension or HNSW index missing")
        except Exception:
            return DependencyStatus(status="unavailable", detail="vector readiness query failed")

    async def _ollama_status(self) -> DependencyStatus:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{self._settings.ollama_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
            return DependencyStatus(status="ok")
        except httpx.HTTPError:
            return DependencyStatus(status="unavailable", detail="Ollama is unreachable")
