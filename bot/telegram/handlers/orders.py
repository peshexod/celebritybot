from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories import OrderRepository, UserRepository
from bot.telegram.keyboards import orders_keyboard


router = Router()

STATUS_MAP = {
    "pending_payment": "⏳ Ожидает оплаты",
    "paid": "💳 Оплачен",
    "generating_audio": "🔄 Генерация аудио",
    "generating_video": "🔄 Генерируется",
    "retrying": "🔄 Повторная попытка",
    "completed": "✅ Готово",
    "refunded": "💸 Возврат средств",
    "failed": "❌ Ошибка",
}


async def _send_user_orders(message: Message, session: AsyncSession) -> bool:
    user = await UserRepository(session).get_or_create_telegram_user(message.from_user.id, message.from_user.username)
    orders = await OrderRepository(session).list_user_orders(user.id, page=0)
    if not orders:
        await message.answer("У вас пока нет заказов.")
        return False

    rows = []
    for order in orders:
        status_label = STATUS_MAP.get(order.status.value, order.status.value)
        rows.append(f"#{order.id} | {status_label} | попытка {order.attempt_number}")

    await message.answer("Ваши заказы:\n" + "\n".join(rows), reply_markup=orders_keyboard(orders, 0))
    return True


@router.callback_query(F.data == "my_orders")
async def show_orders(callback: CallbackQuery, session: AsyncSession) -> None:
    await _send_user_orders(callback.message, session)
    await callback.answer()


@router.message(Command("my_orders"))
async def my_orders_command(message: Message, session: AsyncSession) -> None:
    await _send_user_orders(message, session)


@router.callback_query(F.data.startswith("orders_page:"))
async def paginate_orders(callback: CallbackQuery, session: AsyncSession) -> None:
    page = int(callback.data.split(":", 1)[1])
    user = await UserRepository(session).get_or_create_telegram_user(callback.from_user.id, callback.from_user.username)
    orders = await OrderRepository(session).list_user_orders(user.id, page=page)
    if not orders:
        await callback.answer("Нет заказов на этой странице", show_alert=True)
        return
    rows = []
    for order in orders:
        status_label = STATUS_MAP.get(order.status.value, order.status.value)
        rows.append(f"#{order.id} | {status_label} | попытка {order.attempt_number}")
    await callback.message.answer("Ваши заказы:\n" + "\n".join(rows), reply_markup=orders_keyboard(orders, page))
    await callback.answer()


@router.callback_query(F.data.startswith("order:"))
async def show_order_details(callback: CallbackQuery, session: AsyncSession) -> None:
    user = await UserRepository(session).get_or_create_telegram_user(callback.from_user.id, callback.from_user.username)

    try:
        order_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer("Некорректный заказ", show_alert=True)
        return

    order = await OrderRepository(session).get_order(order_id)
    if not order or order.user_id != user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    status_label = STATUS_MAP.get(order.status.value, order.status.value)
    details = [
        f"Заказ #{order.id}",
        f"Статус: {status_label}",
        f"Попытка: {order.attempt_number}/{order.max_attempts}",
        f"Текст: {order.text}",
    ]
    if order.error_message:
        details.append(f"Ошибка: {order.error_message}")

    await callback.message.answer("\n".join(details))
    await callback.answer()
