class HealthAppService:
    async def status(self) -> dict[str, str]:
        return {"status": "ok"}
