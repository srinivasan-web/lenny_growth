from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from collections.abc import Callable

from app.api.dependencies import get_chat_service_factory
from app.models.schemas import ChatRequest
from app.services.chat import ChatService
from app.services.sessions import SessionNotFoundError

router = APIRouter(tags=["chat"])


@router.post("/chat", response_class=StreamingResponse)
async def chat(payload: ChatRequest, service_factory: Callable[[str | None], ChatService] = Depends(get_chat_service_factory)) -> StreamingResponse:
    service = service_factory(payload.provider)
    try:
        await service.ensure_session(payload.session_id)
    except SessionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.") from error
    return StreamingResponse(service.stream(payload.session_id, payload.message), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
