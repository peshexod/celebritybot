from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import Platform
from bot.db.repositories import OrderRepository, UserRepository
from bot.services.ai_service import AIService
from bot.telegram.keyboards import occasion_keyboard, text_approval_keyboard, text_choice_keyboard
from bot.telegram.states import GreetingFSM


router = Router()
settings = get_settings()
ai_service = AIService()


@router.callback_query(F.data == "create_greeting")
async def create_greeting_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(GreetingFSM.waiting_text_choice)
    await callback.message.answer("Выберите способ ввода текста:", reply_markup=text_choice_keyboard())
    await callback.answer()


@router.message(Command("create_present"))
async def create_present_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(GreetingFSM.waiting_text_choice)
    await message.answer("Выберите способ ввода текста:", reply_markup=text_choice_keyboard())


@router.callback_query(F.data == "own_text", GreetingFSM.waiting_text_choice)
async def choose_own_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GreetingFSM.waiting_own_text)
    await callback.message.answer("Отправьте текст поздравления (до 500 символов).")
    await callback.answer()


@router.message(GreetingFSM.waiting_own_text)
async def handle_own_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if len(message.text or "") > settings.max_text_length:
        await message.answer(f"Текст слишком длинный. Максимум {settings.max_text_length} символов.")
        return

    data = await state.get_data()
    order_repo = OrderRepository(session)

    existing_order_id = data.get("order_id")
    if existing_order_id:
        await order_repo.update_order_text(int(existing_order_id), message.text)
        order_id = int(existing_order_id)
    else:
        user = await UserRepository(session).get_or_create_telegram_user(message.from_user.id, message.from_user.username)
        order = await order_repo.create_order(user.id, message.text, settings.order_price, Platform.telegram)
        order_id = order.id

    await state.update_data(order_id=order_id, final_text=message.text)
    await state.set_state(GreetingFSM.waiting_text_approval)
    await message.answer(f"Текст для согласования:\n\n{message.text}", reply_markup=text_approval_keyboard())


@router.callback_query(F.data == "ai_text", GreetingFSM.waiting_text_choice)
async def choose_ai_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GreetingFSM.waiting_recipient_name)
    await state.update_data(regen_attempts=0)
    await callback.message.answer("Как зовут получателя?")
    await callback.answer()


@router.message(GreetingFSM.waiting_recipient_name)
async def collect_recipient(message: Message, state: FSMContext) -> None:
    await state.update_data(recipient_name=message.text)
    await state.set_state(GreetingFSM.waiting_occasion)
    await message.answer("Какой повод?", reply_markup=occasion_keyboard())


@router.callback_query(F.data.startswith("occasion:"), GreetingFSM.waiting_occasion)
async def collect_occasion(callback: CallbackQuery, state: FSMContext) -> None:
    occasion = callback.data.split(":", 1)[1]
    await state.update_data(occasion=occasion)
    await state.set_state(GreetingFSM.waiting_details)
    await callback.message.answer("Хотите добавить детали или пожелания? Напишите текст или отправьте 'Пропустить'.")
    await callback.answer()


@router.message(GreetingFSM.waiting_details)
async def generate_ai_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    details = "" if message.text and message.text.lower() == "пропустить" else (message.text or "")
    data = await state.get_data()
    await message.answer("Генерирую текст...")
    text = await ai_service.generate_greeting(data["recipient_name"], data["occasion"], details)

    user = await UserRepository(session).get_or_create_telegram_user(message.from_user.id, message.from_user.username)
    order = await OrderRepository(session).create_order(user.id, text, settings.order_price, Platform.telegram)
    await state.update_data(order_id=order.id, final_text=text, details=details)
    await state.set_state(GreetingFSM.waiting_text_approval)
    await message.answer(f"Вариант поздравления:\n\n{text}", reply_markup=text_approval_keyboard())


@router.callback_query(F.data == "text_retry", GreetingFSM.waiting_text_approval)
async def retry_text(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    attempts = int(data.get("regen_attempts", 0)) + 1
    if attempts >= settings.max_regen_attempts:
        await state.set_state(GreetingFSM.waiting_own_text)
        await callback.message.answer("Достигнут лимит попыток. Введите текст вручную.")
        await callback.answer()
        return
    text = await ai_service.generate_greeting(data["recipient_name"], data["occasion"], data.get("details"))
    await state.update_data(regen_attempts=attempts, final_text=text)
    await callback.message.answer(f"Новый вариант:\n\n{text}", reply_markup=text_approval_keyboard())
    await callback.answer()


@router.callback_query(F.data == "text_edit", GreetingFSM.waiting_text_approval)
async def edit_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GreetingFSM.waiting_own_text)
    await callback.message.answer("Отправьте отредактированный текст.")
    await callback.answer()
