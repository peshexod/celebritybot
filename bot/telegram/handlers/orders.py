from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Platform
from bot.handlers.shared import get_user_order_details_common, get_user_orders_common
from bot.texts import (
    ORDER_INVALID_TEXT,
    ORDER_NOT_FOUND_TEXT,
    ORDERS_EMPTY_TEXT,
    ORDERS_PAGE_EMPTY_TEXT,
    order_details_text,
    order_row_text,
    orders_text,
)
from bot.telegram.keyboards import orders_keyboard


router = Router()


async def _send_user_orders(message: Message, session: AsyncSession, page: int = 0) -> bool:
    orders = await get_user_orders_common(
        user_id=message.from_user.id,
        username=message.from_user.username,
        platform=Platform.telegram,
        session=session,
        page=page,
    )
    if not orders:
        if page == 0:
            await message.answer(ORDERS_EMPTY_TEXT)
        return False

    rows = [order_row_text(order.id, order.status.value, order.attempt_number) for order in orders]
    await message.answer(orders_text(rows), reply_markup=orders_keyboard(orders, page))
    return True


@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery, session: AsyncSession) -> None:
    await _send_user_orders(callback.message, session, page=0)
    await callback.answer()


@router.message(Command("my_orders"))
async def my_orders_command(message: Message, session: AsyncSession) -> None:
    await _send_user_orders(message, session, page=0)


@router.callback_query(F.data.startswith("orders_page:"))
async def paginate_orders(callback: CallbackQuery, session: AsyncSession) -> None:
    page = int(callback.data.split(":", 1)[1])
    ok = await _send_user_orders(callback.message, session, page=page)
    if not ok:
        await callback.answer(ORDERS_PAGE_EMPTY_TEXT, show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("order:"))
async def show_order_details(callback: CallbackQuery, session: AsyncSession) -> None:
    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer(ORDER_INVALID_TEXT, show_alert=True)
        return

    order = await get_user_order_details_common(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        platform=Platform.telegram,
        order_id=order_id,
        session=session,
    )
    if not order:
        await callback.answer(ORDER_NOT_FOUND_TEXT, show_alert=True)
        return

    await callback.message.answer(
        order_details_text(
            order_id=order.id,
            status=order.status.value,
            attempt=order.attempt_number,
            max_attempts=order.max_attempts,
            text=order.text,
            error=order.error_message,
        )
    )
    await callback.answer()
