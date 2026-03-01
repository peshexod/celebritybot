from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import OrderStatus
from bot.db.repositories import OrderRepository, UserRepository
from bot.telegram.character_browsing import start_character_browsing
from bot.telegram.keyboards import main_menu_keyboard, order_confirm_keyboard
from bot.telegram.states import CharacterFSM


router = Router()


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    await user_repo.get_or_create_telegram_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "Привет! Я помогу создать поздравительный видео-кружок. Выберите действие:",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data == "resume_order")
async def resume_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await UserRepository(session).get_or_create_telegram_user(callback.from_user.id, callback.from_user.username)
    order = await OrderRepository(session).get_latest_user_order(user.id)

    if not order:
        await callback.message.answer("Активных заказов не найдено. Начните новый через «Создать поздравление».")
        await callback.answer()
        return

    if order.status != OrderStatus.pending_payment:
        await callback.message.answer(
            f"Последний заказ #{order.id} уже в статусе {order.status.value}. Откройте «Мои заказы» для деталей."
        )
        await callback.answer()
        return

    await state.clear()
    await state.update_data(order_id=order.id, final_text=order.text)

    if order.character_id and order.creative_id:
        await state.update_data(character_id=order.character_id, creative_id=order.creative_id)
        await state.set_state(CharacterFSM.confirming_order)
        await callback.message.answer(
            f"Восстановлен заказ:\n\n"
            f"Текст: {order.text}\n"
            f"Персонаж ID: {order.character_id}\n"
            f"Образ ID: {order.creative_id}",
            reply_markup=order_confirm_keyboard(),
        )
        await callback.answer("Заказ восстановлен")
        return

    await start_character_browsing(callback, state, session, page=0)
    await callback.answer("Продолжаем с выбора персонажа")


@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "1) Создайте текст вручную или через AI\n"
        "2) Выберите персонажа и образ\n"
        "3) Оплатите заказ\n"
        "4) Дождитесь генерации видео"
    )
    await callback.answer()
