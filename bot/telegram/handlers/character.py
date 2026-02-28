from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories import CharacterRepository, OrderRepository
from bot.telegram.keyboards import characters_keyboard, creative_keyboard, order_confirm_keyboard
from bot.telegram.states import CharacterFSM, GreetingFSM


router = Router()


@router.callback_query(F.data == "text_ok", GreetingFSM.waiting_text_approval)
async def start_character_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    character_repo = CharacterRepository(session)
    page = 0
    characters = await character_repo.list_characters(page=page)
    await state.set_state(CharacterFSM.browsing_characters)
    await state.update_data(character_page=page)
    if not characters:
        await callback.message.answer("Список персонажей пока пуст.")
        await callback.answer()
        return
    for character in characters:
        await callback.message.answer_photo(
            photo=character.preview_image_path,
            caption=f"{character.name}\n{character.description}",
            reply_markup=characters_keyboard(characters, page),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("char_page:"), CharacterFSM.browsing_characters)
async def paginate_characters(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    page = int(callback.data.split(":", 1)[1])
    characters = await CharacterRepository(session).list_characters(page=page)
    if not characters:
        await callback.answer("Больше персонажей нет", show_alert=True)
        return
    await state.update_data(character_page=page)
    for character in characters:
        await callback.message.answer_photo(
            photo=character.preview_image_path,
            caption=f"{character.name}\n{character.description}",
            reply_markup=characters_keyboard(characters, page),
        )
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
    await state.set_state(CharacterFSM.browsing_creatives)
    await callback.message.answer_photo(
        photo=creative.image_path,
        caption=creative.label or "Выберите этот образ",
        reply_markup=creative_keyboard(creative.id, 0),
    )
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
    await state.update_data(creative_page=page)
    await callback.message.answer_photo(
        photo=creative.image_path,
        caption=creative.label or "Выберите этот образ",
        reply_markup=creative_keyboard(creative.id, page),
    )
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
