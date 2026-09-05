from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_session_service
from app.models.schemas import CreateSessionRequest, SessionResponse
from app.services.sessions import SessionNotFoundError, SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(payload: CreateSessionRequest, service: SessionService = Depends(get_session_service)) -> SessionResponse:
    return await service.create(payload.title)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: UUID, service: SessionService = Depends(get_session_service)) -> SessionResponse:
    try:
        return await service.get(session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.") from error
