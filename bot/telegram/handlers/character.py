from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import OrderStatus
from bot.db.repositories import CharacterRepository, OrderRepository, UserRepository
from bot.telegram.character_browsing import show_character_card, start_character_browsing
from bot.telegram.keyboards import creative_keyboard, order_confirm_keyboard
from bot.telegram.states import CharacterFSM, GreetingFSM
from bot.utils.helpers import as_telegram_photo


router = Router()


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
    has_character = await show_character_card(
        callback=callback,
        character_repo=character_repo,
        page=page,
        edit_existing=True,
    )
    if not has_character:
        await callback.answer("Больше персонажей нет", show_alert=True)
        return
    await state.update_data(character_page=page)
    await callback.answer()


@router.callback_query(F.data.startswith("char:"), CharacterFSM.browsing_characters)
async def select_character(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    character_id = int(callback.data.split(":", 1)[1])
    await state.update_data(character_id=character_id, creative_page=0)
    creatives = await CharacterRepository(session).list_creatives(character_id, page=0)
    if not creatives:
        await callback.answer("Для персонажа нет образов", show_alert=True)
        return
    creative = creatives[0]
    character_repo = CharacterRepository(session)
    await state.set_state(CharacterFSM.browsing_creatives)
    message = await callback.message.answer_photo(
        photo=as_telegram_photo(creative.telegram_file_id or creative.image_path),
        caption=creative.label or "Выберите этот образ",
        reply_markup=creative_keyboard(creative.id, 0),
    )
    if not creative.telegram_file_id and message.photo:
        await character_repo.set_creative_telegram_file_id(creative.id, message.photo[-1].file_id)
    await callback.answer()


@router.callback_query(F.data.startswith("creative_page:"), CharacterFSM.browsing_creatives)
async def paginate_creatives(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    character_id = int(data["character_id"])
    page = int(callback.data.split(":", 1)[1])
    creatives = await CharacterRepository(session).list_creatives(character_id, page=page)
    if not creatives:
        await callback.answer("Больше образов нет", show_alert=True)
        return
    creative = creatives[0]
    character_repo = CharacterRepository(session)
    await state.update_data(creative_page=page)
    message = await callback.message.answer_photo(
        photo=as_telegram_photo(creative.telegram_file_id or creative.image_path),
        caption=creative.label or "Выберите этот образ",
        reply_markup=creative_keyboard(creative.id, page),
    )
    if not creative.telegram_file_id and message.photo:
        await character_repo.set_creative_telegram_file_id(creative.id, message.photo[-1].file_id)
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
    await callback.message.answer(
        f"Проверьте заказ:\n\n"
        f"Текст: {data.get('final_text', '')}\n"
        f"Персонаж ID: {character_id}\n"
        f"Образ ID: {creative_id}",
        reply_markup=order_confirm_keyboard(),
    )
    await callback.answer()
