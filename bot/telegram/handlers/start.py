from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.shared import handle_resume_order_common, handle_start_common
from bot.db.models import Platform
from bot.telegram.character_browsing import start_character_browsing
from bot.telegram.keyboards import main_menu_keyboard, order_confirm_keyboard
from bot.telegram.states import CharacterFSM
from bot.texts import (
    GREETING_TEXT,
    HELP_TEXT,
    NO_ACTIVE_ORDER_TEXT,
    order_processed_text,
    resumed_order_text,
)


router = Router()

async def _resume_order_flow(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    callback: CallbackQuery | None = None,
) -> None:
    result = await handle_resume_order_common(
        user_id=message.from_user.id,
        username=message.from_user.username,
        platform=Platform.telegram,
        session=session,
    )

    if result.kind == "missing":
        await message.answer(NO_ACTIVE_ORDER_TEXT)
        return

    if result.kind == "unavailable":
        await message.answer(order_processed_text(result.order_id or 0, result.status or "unknown"))
        return

    await state.clear()
    await state.update_data(order_id=result.order_id, final_text=result.text or "")

    if result.kind == "confirm_ready":
        await state.update_data(character_id=result.character_id, creative_id=result.creative_id)
        await state.set_state(CharacterFSM.confirming_order)
        await message.answer(
            resumed_order_text(
                result.text or "",
                result.character_name or str(result.character_id or "-"),
                result.creative_label or str(result.creative_id or "-"),
            ),
            reply_markup=order_confirm_keyboard(),
        )
        return

    if callback is not None:
        await start_character_browsing(callback, state, session, page=0)
        return

    await start_character_browsing(message, state, session, page=0)


@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    await handle_start_common(message.from_user.id, message.from_user.username, Platform.telegram, session)
    await message.answer(GREETING_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "resume_order")
async def resume_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await _resume_order_flow(callback.message, state, session, callback=callback)
    await callback.answer()


@router.message(Command("continue_order"))
async def continue_order_command(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _resume_order_flow(message, state, session)


@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery) -> None:
    await callback.message.answer(HELP_TEXT)
    await callback.answer()


@router.message(Command("help"))
async def help_command_handler(message: Message) -> None:
    await message.answer(HELP_TEXT)
