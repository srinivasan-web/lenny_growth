from fastapi import APIRouter, Depends

from app.api.dependencies import get_health_service
from app.models.schemas import HealthResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    return await service.check()
