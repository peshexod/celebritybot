from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle.bot import Message

from bot.handlers.shared import get_user_order_details_common, get_user_orders_common
from bot.handlers.vk import labeler
from bot.texts import (
    ORDER_INVALID_TEXT,
    ORDER_NOT_FOUND_TEXT,
    ORDERS_EMPTY_TEXT,
    ORDERS_PAGE_EMPTY_TEXT,
    order_details_text,
    order_row_text,
    orders_text,
)
from bot.vk.helpers import answer_message, extract_payload, payload_command
from bot.vk.keyboards import orders_keyboard_vk


MY_ORDERS_COMMANDS = {"/my_orders", "мои заказы"}


async def _send_orders(message: Message, session: AsyncSession, page: int = 0) -> bool:
    orders = await get_user_orders_common(
        user_id=message.from_id,
        username=None,
        platform="vk",
        session=session,
        page=page,
    )
    if not orders:
        await answer_message(message, ORDERS_EMPTY_TEXT if page == 0 else ORDERS_PAGE_EMPTY_TEXT)
        return False

    rows = [order_row_text(order.id, order.status.value, order.attempt_number) for order in orders]
    await answer_message(message, orders_text(rows), keyboard=orders_keyboard_vk(orders, page))
    return True


@labeler.message()
async def orders_handler(message: Message, session: AsyncSession) -> None:
    text = (message.text or "").strip().lower()
    command = payload_command(message)
    payload = extract_payload(message)

    if text in MY_ORDERS_COMMANDS or command == "my_orders":
        await _send_orders(message, session, page=0)
        return

    if command == "orders_page":
        await _send_orders(message, session, page=int(payload.get("page", 0)))
        return

    if command != "order":
        return

    try:
        order_id = int(payload["order_id"])
    except (KeyError, TypeError, ValueError):
        await answer_message(message, ORDER_INVALID_TEXT)
        return

    order = await get_user_order_details_common(
        user_id=message.from_id,
        username=None,
        platform="vk",
        order_id=order_id,
        session=session,
    )
    if not order:
        await answer_message(message, ORDER_NOT_FOUND_TEXT)
        return

    await answer_message(
        message,
        order_details_text(
            order_id=order.id,
            status=order.status.value,
            attempt=order.attempt_number,
            max_attempts=order.max_attempts,
            text=order.text,
            error=order.error_message,
        ),
    )
