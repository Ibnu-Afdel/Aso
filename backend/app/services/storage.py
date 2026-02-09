class StorageService:
    async def put(self, key: str, value: bytes) -> None:
        _ = key, value
