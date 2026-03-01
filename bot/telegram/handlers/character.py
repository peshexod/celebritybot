from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import OrderStatus
from bot.db.repositories import CharacterRepository, OrderRepository, UserRepository
from bot.telegram.character_browsing import show_character_card, start_character_browsing
from bot.telegram.keyboards import creative_keyboard, order_confirm_keyboard
from bot.telegram.states import CharacterFSM, GreetingFSM
from bot.utils.helpers import as_telegram_photo


router = Router()


async def _show_creative_card(
    callback: CallbackQuery,
    character_repo: CharacterRepository,
    character_id: int,
    page: int,
    edit_existing: bool,
) -> int | None:
    total_creatives = await character_repo.count_creatives(character_id)
    if total_creatives == 0:
        return None

    normalized_page = page % total_creatives
    creatives = await character_repo.list_creatives(character_id, page=normalized_page)
    if not creatives:
        return None

    creative = creatives[0]
    base_label = creative.label or "Выберите этот образ"
    caption = f"{base_label} ({normalized_page + 1}/{total_creatives})"
    media = InputMediaPhoto(media=as_telegram_photo(creative.telegram_file_id or creative.image_path), caption=caption)

    if edit_existing:
        try:
            result = await callback.message.edit_media(
                media=media,
                reply_markup=creative_keyboard(creative.id, normalized_page),
            )
        except TelegramBadRequest as exc:
            if "message is not modified" not in str(exc).lower():
                raise
            result = None
    else:
        result = await callback.message.answer_photo(
            photo=as_telegram_photo(creative.telegram_file_id or creative.image_path),
            caption=caption,
            reply_markup=creative_keyboard(creative.id, normalized_page),
        )

    if not creative.telegram_file_id:
        sent_message = result if isinstance(result, Message) else None
        if sent_message and sent_message.photo:
            await character_repo.set_creative_telegram_file_id(creative.id, sent_message.photo[-1].file_id)

    return normalized_page


@router.callback_query(F.data == "text_ok", GreetingFSM.waiting_text_approval)
async def start_character_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await start_character_browsing(callback, state, session, page=0)
    await callback.answer()


@router.callback_query(StateFilter(None), F.data == "text_ok")
async def start_character_choice_recover(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    user = await UserRepository(session).get_or_create_telegram_user(callback.from_user.id, callback.from_user.username)
    order = await OrderRepository(session).get_latest_user_order(user.id)

    if not order or order.status != OrderStatus.pending_payment:
        await callback.message.answer("Контекст предыдущего шага утерян. Нажмите «Создать поздравление» или «Продолжить заказ».")
        await callback.answer()
        return

    await state.clear()
    await state.update_data(order_id=order.id, final_text=order.text)

    await start_character_browsing(callback, state, session, page=0)
    await callback.answer("Продолжаем выбор персонажа")


@router.callback_query(F.data.startswith("char_page:"), CharacterFSM.browsing_characters)
async def paginate_characters(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    page = int(callback.data.split(":", 1)[1])
    character_repo = CharacterRepository(session)
    normalized_page = await show_character_card(
        callback=callback,
        character_repo=character_repo,
        page=page,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer("Больше персонажей нет", show_alert=True)
        return
    await state.update_data(character_page=normalized_page)
    await callback.answer()


@router.callback_query(F.data.startswith("char:"), CharacterFSM.browsing_characters)
async def select_character(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    character_id = int(callback.data.split(":", 1)[1])
    await state.update_data(character_id=character_id, creative_page=0)
    character_repo = CharacterRepository(session)
    normalized_page = await _show_creative_card(
        callback=callback,
        character_repo=character_repo,
        character_id=character_id,
        page=0,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer("Для персонажа нет образов", show_alert=True)
        return

    await state.set_state(CharacterFSM.browsing_creatives)
    await state.update_data(creative_page=normalized_page)
    await callback.answer()


@router.callback_query(F.data.startswith("creative_page:"), CharacterFSM.browsing_creatives)
async def paginate_creatives(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    character_id = int(data["character_id"])
    page = int(callback.data.split(":", 1)[1])
    character_repo = CharacterRepository(session)
    normalized_page = await _show_creative_card(
        callback=callback,
        character_repo=character_repo,
        character_id=character_id,
        page=page,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer("Больше образов нет", show_alert=True)
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
        await callback.message.answer("Не удалось восстановить выбранного персонажа. Выберите его заново.")
        await start_character_browsing(callback, state, session, page=0)
        await callback.answer()
        return

    page = int(data.get("creative_page", 0))
    character_repo = CharacterRepository(session)
    normalized_page = await _show_creative_card(
        callback=callback,
        character_repo=character_repo,
        character_id=int(character_id),
        page=page,
        edit_existing=True,
    )
    if normalized_page is None:
        await callback.answer("Для персонажа нет образов", show_alert=True)
        return

    await state.set_state(CharacterFSM.browsing_creatives)
    await state.update_data(creative_page=normalized_page)
    await callback.answer()


@router.callback_query(F.data == "change_text", CharacterFSM.confirming_order)
async def change_text(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(GreetingFSM.waiting_own_text)
    await callback.message.answer("Отправьте новый текст поздравления (до 500 символов).")
    await callback.answer()


@router.callback_query(F.data.startswith("creative:"), CharacterFSM.browsing_creatives)
async def confirm_order(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    creative_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    order_id = int(data["order_id"])
    character_id = int(data["character_id"])
    await OrderRepository(session).update_order_selection(order_id, character_id, creative_id)
    await state.update_data(creative_id=creative_id)
    await state.set_state(CharacterFSM.confirming_order)
    confirmation_text = (
        f"Проверьте заказ:\n\n"
        f"Текст: {data.get('final_text', '')}\n"
        f"Персонаж ID: {character_id}\n"
        f"Образ ID: {creative_id}"
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
