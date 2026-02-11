from fastapi import APIRouter

from app.services.health import HealthAppService

router = APIRouter()
health_app_service = HealthAppService()


@router.get("/health")
async def health_check():
    return await health_app_service.status()
