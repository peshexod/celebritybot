from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import Platform
from bot.handlers.shared import (
    TextTooLongError,
    handle_ai_generation_common,
    handle_choose_ai_text_common,
    handle_choose_own_text_common,
    regenerate_ai_text_common,
    save_own_text_common,
)
from bot.texts import (
    DETAILS_PROMPT,
    EDITED_TEXT_PROMPT,
    GENERATING_TEXT,
    MAX_REGEN_ATTEMPTS_TEXT,
    OCCASION_PROMPT,
    RECIPIENT_NAME_PROMPT,
    TEXT_CHOICE_TEXT,
    own_text_prompt,
    text_approval_text,
    text_too_long_text,
)
from bot.telegram.keyboards import occasion_keyboard, text_approval_keyboard, text_choice_keyboard
from bot.telegram.states import GreetingFSM


router = Router()
settings = get_settings()


@router.callback_query(F.data == "create_greeting")
async def create_greeting_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(GreetingFSM.waiting_text_choice)
    await callback.message.answer(TEXT_CHOICE_TEXT, reply_markup=text_choice_keyboard())
    await callback.answer()


@router.message(Command("create_present"))
async def create_present_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(GreetingFSM.waiting_text_choice)
    await message.answer(TEXT_CHOICE_TEXT, reply_markup=text_choice_keyboard())


@router.callback_query(F.data == "own_text", GreetingFSM.waiting_text_choice)
async def choose_own_text(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await handle_choose_own_text_common(callback.from_user.id, callback.from_user.username, Platform.telegram, session)
    await state.set_state(GreetingFSM.waiting_own_text)
    await callback.message.answer(own_text_prompt(settings.max_text_length))
    await callback.answer()


@router.message(GreetingFSM.waiting_own_text)
async def handle_own_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        result = await save_own_text_common(
            user_id=message.from_user.id,
            username=message.from_user.username,
            platform=Platform.telegram,
            text=message.text or "",
            session=session,
            existing_order_id=int(data["order_id"]) if data.get("order_id") else None,
        )
    except TextTooLongError:
        await message.answer(text_too_long_text(settings.max_text_length))
        return

    await state.update_data(order_id=result.order.id, final_text=result.text)
    await state.set_state(GreetingFSM.waiting_text_approval)
    await message.answer(text_approval_text(result.text), reply_markup=text_approval_keyboard())


@router.callback_query(F.data == "ai_text", GreetingFSM.waiting_text_choice)
async def choose_ai_text(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await handle_choose_ai_text_common(callback.from_user.id, callback.from_user.username, Platform.telegram, session)
    await state.set_state(GreetingFSM.waiting_recipient_name)
    await state.update_data(regen_attempts=0)
    await callback.message.answer(RECIPIENT_NAME_PROMPT)
    await callback.answer()


@router.message(GreetingFSM.waiting_recipient_name)
async def collect_recipient(message: Message, state: FSMContext) -> None:
    await state.update_data(recipient_name=message.text)
    await state.set_state(GreetingFSM.waiting_occasion)
    await message.answer(OCCASION_PROMPT, reply_markup=occasion_keyboard())


@router.callback_query(F.data.startswith("occasion:"), GreetingFSM.waiting_occasion)
async def collect_occasion(callback: CallbackQuery, state: FSMContext) -> None:
    occasion = callback.data.split(":", 1)[1]
    await state.update_data(occasion=occasion)
    await state.set_state(GreetingFSM.waiting_details)
    await callback.message.answer(DETAILS_PROMPT)
    await callback.answer()


@router.message(GreetingFSM.waiting_details)
async def generate_ai_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    details = "" if message.text and message.text.lower() == "пропустить" else (message.text or "")
    data = await state.get_data()
    await message.answer(GENERATING_TEXT)
    result = await handle_ai_generation_common(
        user_id=message.from_user.id,
        username=message.from_user.username,
        platform=Platform.telegram,
        recipient_name=data["recipient_name"],
        occasion=data["occasion"],
        details=details,
        session=session,
        existing_order_id=int(data["order_id"]) if data.get("order_id") else None,
    )
    await state.update_data(order_id=result.order.id, final_text=result.text, details=details)
    await state.set_state(GreetingFSM.waiting_text_approval)
    await message.answer(text_approval_text(result.text, ai_generated=True), reply_markup=text_approval_keyboard())


@router.callback_query(F.data == "text_retry", GreetingFSM.waiting_text_approval)
async def retry_text(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    attempts = int(data.get("regen_attempts", 0)) + 1
    if attempts >= settings.max_regen_attempts:
        await state.set_state(GreetingFSM.waiting_own_text)
        await callback.message.answer(MAX_REGEN_ATTEMPTS_TEXT)
        await callback.answer()
        return
    text = await regenerate_ai_text_common(
        order_id=int(data["order_id"]),
        recipient_name=data["recipient_name"],
        occasion=data["occasion"],
        details=data.get("details", ""),
        session=session,
    )
    await state.update_data(regen_attempts=attempts, final_text=text)
    await callback.message.answer(text_approval_text(text, regenerated=True), reply_markup=text_approval_keyboard())
    await callback.answer()


@router.callback_query(F.data == "text_edit", GreetingFSM.waiting_text_approval)
async def edit_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GreetingFSM.waiting_own_text)
    await callback.message.answer(EDITED_TEXT_PROMPT)
    await callback.answer()
