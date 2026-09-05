from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Message, Session
from app.models.schemas import MessageResponse, SessionResponse


class SessionNotFoundError(Exception):
    pass


class SessionService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, title: str | None) -> SessionResponse:
        session = Session(title=title.strip() if title else None)
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return SessionResponse(id=session.id, title=session.title, created_at=session.created_at, updated_at=session.updated_at, messages=[])

    async def get(self, session_id: UUID) -> SessionResponse:
        session = await self._db.get(Session, session_id)
        if session is None:
            raise SessionNotFoundError(f"Session {session_id} was not found.")
        messages = (await self._db.scalars(select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc()))).all()
        return SessionResponse(
            id=session.id,
            title=session.title,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=[MessageResponse(id=message.id, role=message.role, content=message.content, provider=message.provider, model=message.model, source_metadata=message.source_metadata, created_at=message.created_at) for message in messages],
        )
