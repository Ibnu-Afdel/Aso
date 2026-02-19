from aiogram import Router, types
from aiogram.filters import CommandStart

from app.services.users import UserAppService

router = Router()


@router.message(CommandStart())
async def start_handler(
    message: types.Message,
    user_app_service: UserAppService,
):
    if not message.from_user:
        return

    await user_app_service.ensure_user(telegram_id=message.from_user.id)

    await message.answer("Hello! Your account is registered.")
