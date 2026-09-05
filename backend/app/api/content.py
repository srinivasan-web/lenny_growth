from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_ship30_service_factory
from app.models.schemas import Ship30Request, Ship30Response
from app.services.ship30 import Ship30ContentService, Ship30GenerationError, Ship30ValidationError

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/ship-30", response_model=Ship30Response)
async def ship30_content(
    payload: Ship30Request,
    service_factory: Callable[[str | None], Ship30ContentService] = Depends(get_ship30_service_factory),
) -> Ship30Response:
    service = service_factory(payload.provider)
    try:
        artifact = await service.generate(payload.topic)
    except Ship30ValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
    except Ship30GenerationError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return Ship30Response(
        markdown=artifact.markdown,
        word_count=artifact.word_count,
        sources=[source.model_dump(mode="json") for source in artifact.sources],
        provider=artifact.provider,
        model=artifact.model,
    )