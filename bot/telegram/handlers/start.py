from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories import UserRepository
from bot.telegram.keyboards import main_menu_keyboard


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    await user_repo.get_or_create_telegram_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "Привет! Я помогу создать поздравительный видео-кружок. Выберите действие:",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "1) Создайте текст вручную или через AI\n"
        "2) Выберите персонажа и образ\n"
        "3) Оплатите заказ\n"
        "4) Дождитесь генерации видео"
    )
    await callback.answer()
