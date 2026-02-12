from fastapi import APIRouter

from app.bootstrap.container import get_health_app_service

router = APIRouter()


@router.get("/health")
async def health_check():
    return await get_health_app_service().status()
