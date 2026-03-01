from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories import CharacterRepository
from bot.telegram.keyboards import characters_keyboard
from bot.telegram.states import CharacterFSM
from bot.utils.helpers import as_telegram_photo


async def show_character_card(
    callback: CallbackQuery,
    character_repo: CharacterRepository,
    page: int,
    edit_existing: bool,
) -> int | None:
    total_characters = await character_repo.count_characters()
    if total_characters == 0:
        return None

    normalized_page = page % total_characters
    characters = await character_repo.list_characters(page=normalized_page, page_size=1)
    if not characters:
        return None

    character = characters[0]
    creatives = await character_repo.list_creatives(character.id, page=0)
    first_creative = creatives[0] if creatives else None
    preview_source = (
        first_creative.telegram_file_id or first_creative.image_path
        if first_creative
        else character.preview_image_path
    )

    caption = f"{character.name} ({normalized_page + 1}/{total_characters})\n{character.description}"
    reply_markup = characters_keyboard([character], normalized_page)
    media = InputMediaPhoto(media=as_telegram_photo(preview_source), caption=caption)

    if edit_existing:
        try:
            result = await callback.message.edit_media(media=media, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
            result = None
    else:
        result = await callback.message.answer_photo(
            photo=as_telegram_photo(preview_source),
            caption=caption,
            reply_markup=reply_markup,
        )

    if first_creative and not first_creative.telegram_file_id:
        sent_message = result if isinstance(result, Message) else None
        if sent_message and sent_message.photo:
            await character_repo.set_creative_telegram_file_id(first_creative.id, sent_message.photo[-1].file_id)

    return normalized_page


async def start_character_browsing(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    page: int = 0,
) -> bool:
    character_repo = CharacterRepository(session)
    normalized_page = await show_character_card(
        callback=callback,
        character_repo=character_repo,
        page=page,
        edit_existing=False,
    )
    if normalized_page is None:
        await callback.message.answer("Список персонажей пока пуст.")
        return False

    await state.set_state(CharacterFSM.browsing_characters)
    await state.update_data(character_page=normalized_page)
    return True
