from fastapi import APIRouter, Depends

from app.bootstrap.container import get_health_app_service
from app.services.health import HealthAppService

router = APIRouter()


@router.get("/health")
async def health_check(
    svc: HealthAppService = Depends(get_health_app_service),
):
    return await svc.status()
