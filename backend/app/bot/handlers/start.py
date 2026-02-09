from aiogram import Router, types
from aiogram.filters import CommandStart

from app.core.db import async_session_maker
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService

router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message):
    if not message.from_user:
        return

    async with async_session_maker() as session:
        repo = UserRepository(session)
        service = UserService(repo)
        await service.ensure_user(telegram_id=message.from_user.id)

    await message.answer("Hello! Your account is registered.")
