from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import OrderStatus
from bot.db.repositories import OrderRepository, PaymentRepository
from bot.services.payment_service import PaymentService
from bot.telegram.keyboards import payment_url_keyboard
from bot.telegram.states import PaymentFSM


router = Router()
settings = get_settings()
payment_service = PaymentService()


@router.callback_query(F.data == "pay_order")
async def create_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    order_id = int(data["order_id"])
    amount = Decimal(settings.order_price)
    payment_id, payment_url = await payment_service.create_payment(
        order_id=order_id,
        amount=amount,
        description=f"Оплата заказа #{order_id}",
        return_url=settings.webhook_host,
    )
    await PaymentRepository(session).create_payment(order_id, payment_id, amount)
    await OrderRepository(session).set_payment_reference(order_id, payment_id)
    await OrderRepository(session).set_status(order_id, OrderStatus.pending_payment)
    await state.set_state(PaymentFSM.waiting_payment)
    await callback.message.answer(
        "Для продолжения оплатите заказ. После оплаты мы подтвердим платёж автоматически в фоне.",
        reply_markup=payment_url_keyboard(payment_url),
    )
    await callback.answer()
