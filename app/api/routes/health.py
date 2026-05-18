from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.bootstrap.container import get_health_app_service
from app.services.health import HealthAppService

router = APIRouter()


@router.get("/healthz")
async def liveness():
    return {"status": "ok"}


@router.get("/readyz")
async def readiness(svc: HealthAppService = Depends(get_health_app_service)):
    result = await svc.readiness()
    if result["status"] != "ok":
        return JSONResponse(status_code=503, content=result)
    return result
