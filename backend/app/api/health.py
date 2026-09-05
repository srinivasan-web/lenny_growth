from fastapi import APIRouter, Depends, Response

from app.api.dependencies import get_health_service
from app.models.schemas import HealthResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/")
async def service_root() -> dict[str, str]:
    return {"service": "lenny-growth-assistant-api", "status": "running", "health": "/api/health"}


@router.get("/favicon.ico", status_code=204)
async def favicon() -> Response:
    return Response(status_code=204)


@router.get("/health", response_model=HealthResponse)
async def health_check(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return await service.check()
