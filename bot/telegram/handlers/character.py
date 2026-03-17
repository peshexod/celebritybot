from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.handlers.shared import (
    get_creatives_page_common,
    handle_resume_order_common,
    select_character_common,
    select_creative_common,
)
from bot.db.models import Platform
from bot.db.repositories import CharacterRepository
from bot.texts import (
    CHARACTER_RESTORE_FAILED_TEXT,
    CONTINUE_CHARACTER_CHOICE_TEXT,
    NO_CREATIVES_TEXT,
    NO_MORE_CHARACTERS_TEXT,
    NO_MORE_CREATIVES_TEXT,
    ORDER_CONTEXT_LOST_TEXT,
    change_text_prompt,
    creative_caption,
    order_confirmation_text,
)
from bot.telegram.character_browsing import show_character_card, start_character_browsing
from bot.telegram.keyboards import creative_keyboard, order_confirm_keyboard
from bot.telegram.states import CharacterFSM, GreetingFSM
from bot.utils.helpers import as_telegram_photo


router = Router()
settings = get_settings()


async def _show_creative_card(
    callback: CallbackQuery,
    session: AsyncSession,
    character_id: int,
    page: int,
    edit_existing: bool,
) -> int | None:
    page_result = await get_creatives_page_common(character_id, page, session)
    if page_result is None:
        return None

    creative = page_result.creative
    caption = creative_caption(creative.label, page_result.page, page_result.total)
    media = InputMediaPhoto(media=as_telegram_photo(creative.telegram_file_id or creative.image_path), caption=caption)

    if edit_existing:
        try:
            sent = await callback.message.edit_media(
                media=media,
                reply_markup=creative_keyboard(creative.id, page_result.page),
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
            sent = None
    else:
        sent = await callback.message.answer_photo(
            photo=as_telegram_photo(creative.telegram_file_id or creative.image_path),
            caption=caption,
            reply_markup=creative_keyboard(creative.id, page_result.page),
        )

    if not creative.telegram_file_id:
        character_repo = CharacterRepository(session)
        sent_message = sent if isinstance(sent, Message) else None
        if sent_message and sent_message.photo:
            await character_repo.set_creative_telegram_file_id(creative.id, sent_message.photo[-1].file_id)

    return page_result.page


@router.callback_query(F.data == "text_ok", GreetingFSM.waiting_text_approval)
async def start_character_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await start_character_browsing(callback, state, session, page=0)
    await callback.answer()


@router.callback_query(StateFilter(None), F.data == "text_ok")
async def start_character_choice_recover(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await handle_resume_order_common(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        platform=Platform.telegram,
        session=session,
    )

    if result.kind in {"missing", "unavailable"}:
        await callback.message.answer(ORDER_CONTEXT_LOST_TEXT)
        await callback.answer()
        return

    await state.clear()
    await state.update_data(order_id=result.order_id, final_text=result.text or "")

    await start_character_browsing(callback, state, session, page=0)
    await callback.answer(CONTINUE_CHARACTER_CHOICE_TEXT)


@router.callback_query(F.data.startswith("char_page:"), CharacterFSM.browsing_characters)
async def paginate_characters(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    page = int(callback.data.split(":", 1)[1])
    normalized_page = await show_character_card(
        target=callback,
        session=session,
        page=page,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer(NO_MORE_CHARACTERS_TEXT, show_alert=True)
        return
    await state.update_data(character_page=normalized_page)
    await callback.answer()


@router.callback_query(F.data.startswith("char:"), CharacterFSM.browsing_characters)
async def select_character(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    character_id = int(callback.data.split(":", 1)[1])
    await state.update_data(character_id=character_id, creative_page=0)
    result = await select_character_common(character_id, session)
    if result is None:
        await callback.answer(NO_CREATIVES_TEXT, show_alert=True)
        return

    normalized_page = await _show_creative_card(
        callback=callback,
        session=session,
        character_id=character_id,
        page=result.page,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer(NO_CREATIVES_TEXT, show_alert=True)
        return

    await state.set_state(CharacterFSM.browsing_creatives)
    await state.update_data(creative_page=normalized_page)
    await callback.answer()


@router.callback_query(F.data.startswith("creative_page:"), CharacterFSM.browsing_creatives)
async def paginate_creatives(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    character_id = int(data["character_id"])
    page = int(callback.data.split(":", 1)[1])
    normalized_page = await _show_creative_card(
        callback=callback,
        session=session,
        character_id=character_id,
        page=page,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer(NO_MORE_CREATIVES_TEXT, show_alert=True)
        return

    await state.update_data(creative_page=normalized_page)
    await callback.answer()


@router.callback_query(F.data == "change_character", CharacterFSM.browsing_creatives)
@router.callback_query(F.data == "change_character", CharacterFSM.confirming_order)
async def change_character(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await start_character_browsing(callback, state, session, page=0)
    await callback.answer()


@router.callback_query(F.data == "change_creative", CharacterFSM.confirming_order)
async def change_creative(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    character_id = data.get("character_id")
    if not character_id:
        await callback.message.answer(CHARACTER_RESTORE_FAILED_TEXT)
        await start_character_browsing(callback, state, session, page=0)
        await callback.answer()
        return

    page = int(data.get("creative_page", 0))
    normalized_page = await _show_creative_card(
        callback=callback,
        session=session,
        character_id=int(character_id),
        page=page,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer(NO_CREATIVES_TEXT, show_alert=True)
        return

    await state.set_state(CharacterFSM.browsing_creatives)
    await state.update_data(creative_page=normalized_page)
    await callback.answer()


@router.callback_query(F.data == "change_text", CharacterFSM.confirming_order)
async def change_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GreetingFSM.waiting_own_text)
    await callback.message.answer(change_text_prompt(settings.max_text_length))
    await callback.answer()


@router.callback_query(F.data.startswith("creative:"), CharacterFSM.browsing_creatives)
async def confirm_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    creative_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    character_id = int(data["character_id"])
    result = await select_creative_common(
        order_id=int(data["order_id"]),
        character_id=character_id,
        creative_id=creative_id,
        session=session,
    )
    if result is None:
        await callback.answer(NO_CREATIVES_TEXT, show_alert=True)
        return

    await state.update_data(creative_id=creative_id)
    await state.set_state(CharacterFSM.confirming_order)
    confirmation_text = order_confirmation_text(
        text=str(data.get("final_text", "")),
        character=result.character.name if result.character else str(character_id),
        creative=result.creative.label or f"Образ #{creative_id}" if result.creative else str(creative_id),
    )
    try:
        await callback.message.edit_caption(
            caption=confirmation_text,
            reply_markup=order_confirm_keyboard(),
        )
    except TelegramBadRequest:
        await callback.message.answer(
            confirmation_text,
            reply_markup=order_confirm_keyboard(),
        )
    await callback.answer()
