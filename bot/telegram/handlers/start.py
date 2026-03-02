from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import OrderStatus
from bot.db.repositories import CharacterRepository, OrderRepository, UserRepository
from bot.telegram.character_browsing import start_character_browsing
from bot.telegram.keyboards import characters_keyboard, main_menu_keyboard, order_confirm_keyboard
from bot.telegram.states import CharacterFSM
from bot.utils.helpers import as_telegram_photo


router = Router()


async def _start_character_browsing_from_message(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    character_repo = CharacterRepository(session)
    total_characters = await character_repo.count_characters()
    if total_characters == 0:
        await message.answer("Список персонажей пока пуст.")
        return

    page = 0
    characters = await character_repo.list_characters(page=page, page_size=1)
    if not characters:
        await message.answer("Список персонажей пока пуст.")
        return

    character = characters[0]
    creatives = await character_repo.list_creatives(character.id, page=0)
    first_creative = creatives[0] if creatives else None
    preview_source = (
        first_creative.telegram_file_id or first_creative.image_path
        if first_creative
        else character.preview_image_path
    )

    sent_message = await message.answer_photo(
        photo=as_telegram_photo(preview_source),
        caption=f"{character.name} (1/{total_characters})\n{character.description}",
        reply_markup=characters_keyboard([character], page),
    )

    if first_creative and not first_creative.telegram_file_id and sent_message.photo:
        await character_repo.set_creative_telegram_file_id(first_creative.id, sent_message.photo[-1].file_id)

    await state.set_state(CharacterFSM.browsing_characters)
    await state.update_data(character_page=page)


async def _resume_order_flow(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    callback: CallbackQuery | None = None,
) -> None:
    user = await UserRepository(session).get_or_create_telegram_user(message.from_user.id, message.from_user.username)
    order = await OrderRepository(session).get_latest_user_order(user.id)

    if not order:
        await message.answer("Активных заказов не найдено. Начните новый через «Создать поздравление».")
        return

    if order.status != OrderStatus.pending_payment:
        await message.answer(
            f"Последний заказ #{order.id} уже в статусе {order.status.value}. Откройте «Мои заказы» для деталей."
        )
        return

    await state.clear()
    await state.update_data(order_id=order.id, final_text=order.text)

    if order.character_id and order.creative_id:
        await state.update_data(character_id=order.character_id, creative_id=order.creative_id)
        await state.set_state(CharacterFSM.confirming_order)
        await message.answer(
            f"Восстановлен заказ:\n\n"
            f"Текст: {order.text}\n"
            f"Персонаж ID: {order.character_id}\n"
            f"Образ ID: {order.creative_id}",
            reply_markup=order_confirm_keyboard(),
        )
        return

    if callback is not None:
        await start_character_browsing(callback, state, session, page=0)
        return

    await _start_character_browsing_from_message(message, state, session)


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
    await _resume_order_flow(callback.message, state, session, callback=callback)
    await callback.answer("Продолжаем с выбора персонажа")


@router.message(Command("continue_order"))
async def continue_order_command(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _resume_order_flow(message, state, session)


@router.callback_query(F.data == "help")
async def help_handler(callback: CallbackQuery) -> None:
    await callback.message.answer(
        "1) Создайте текст вручную или через AI\n"
        "2) Выберите персонажа и образ\n"
        "3) Оплатите заказ\n"
        "4) Дождитесь генерации видео"
    )
    await callback.answer()


@router.message(Command("help"))
async def help_command_handler(message: Message) -> None:
    await message.answer(
        "1) Создайте текст вручную или через AI\n"
        "2) Выберите персонажа и образ\n"
        "3) Оплатите заказ\n"
        "4) Дождитесь генерации видео"
    )
