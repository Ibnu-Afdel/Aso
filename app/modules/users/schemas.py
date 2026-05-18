from datetime import datetime

from pydantic import BaseModel


class UserCreate(BaseModel):
    telegram_id: int


class UserRead(BaseModel):
    id: int
    telegram_id: int
    created_at: datetime

    class Config:
        from_attributes = True
