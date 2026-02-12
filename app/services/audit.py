class AuditService:
    async def log(self, action: str, metadata: dict | None = None) -> None:
        _ = action, metadata
