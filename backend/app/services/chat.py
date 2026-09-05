import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Message, Session
from app.rag.grounded import GroundedRAGEngine, GroundedStreamEvent, RAGError
from app.services.sessions import SessionNotFoundError

logger = logging.getLogger(__name__)


def encode_sse(event: str, payload: object) -> str:
    data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class ChatService:
    def __init__(self, db: AsyncSession, rag: GroundedRAGEngine) -> None:
        self._db, self._rag = db, rag

    async def ensure_session(self, session_id: UUID) -> None:
        if await self._db.get(Session, session_id) is None:
            raise SessionNotFoundError(f"Session {session_id} was not found.")

    async def stream(self, session_id: UUID, content: str) -> AsyncIterator[str]:
        self._db.add(Message(session_id=session_id, role="user", content=content))
        await self._db.commit()
        yield encode_sse("status", {"status": "retrieving"})
        try:
            async for item in self._rag.stream(content):
                if item.event == "done":
                    response = item.data
                    self._db.add(Message(session_id=session_id, role="assistant", content=response.answer, provider=response.retrieval_metadata.provider, model=response.retrieval_metadata.model, source_metadata={"sources": [source.model_dump(mode="json") for source in response.sources]}))
                    await self._db.commit()
                yield encode_sse(item.event, item.data)
        except RAGError as error:
            await self._db.rollback()
            logger.warning("chat_generation_failed: %s", error, exc_info=True, extra={"session_id": str(session_id)})
            yield encode_sse("error", {"message": str(error)})
        except Exception:
            await self._db.rollback()
            logger.exception("chat_stream_failed", extra={"session_id": str(session_id)})
            yield encode_sse("error", {"message": "The backend could not complete the response."})
