from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.shared import get_characters_page_common
from bot.db.repositories import CharacterRepository
from bot.texts import EMPTY_CHARACTERS_TEXT, character_caption
from bot.telegram.keyboards import characters_keyboard
from bot.telegram.states import CharacterFSM
from bot.utils.helpers import as_telegram_photo


async def show_character_card(
    target: Message | CallbackQuery,
    session: AsyncSession,
    page: int,
    edit_existing: bool,
) -> int | None:
    page_result = await get_characters_page_common(page, session)
    if page_result is None:
        return None

    character = page_result.character
    preview_creative = page_result.preview_creative
    preview_source = (
        preview_creative.telegram_file_id or preview_creative.image_path
        if preview_creative
        else page_result.preview_source
    )

    caption = character_caption(character.name, character.description, page_result.page, page_result.total)
    reply_markup = characters_keyboard([character], page_result.page)
    media = InputMediaPhoto(media=as_telegram_photo(preview_source), caption=caption)
    message = target.message if isinstance(target, CallbackQuery) else target

    if edit_existing:
        try:
            result = await message.edit_media(media=media, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
            result = None
    else:
        result = await message.answer_photo(
            photo=as_telegram_photo(preview_source),
            caption=caption,
            reply_markup=reply_markup,
        )

    if preview_creative and not preview_creative.telegram_file_id:
        character_repo = CharacterRepository(session)
        sent_message = result if isinstance(result, Message) else None
        if sent_message and sent_message.photo:
            await character_repo.set_creative_telegram_file_id(preview_creative.id, sent_message.photo[-1].file_id)

    return page_result.page


async def start_character_browsing(
    target: Message | CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    page: int = 0,
) -> bool:
    normalized_page = await show_character_card(
        target=target,
        session=session,
        page=page,
        edit_existing=False,
    )
    if normalized_page is None:
        message = target.message if isinstance(target, CallbackQuery) else target
        await message.answer(EMPTY_CHARACTERS_TEXT)
        return False

    await state.set_state(CharacterFSM.browsing_characters)
    await state.update_data(character_page=normalized_page)
    return True
