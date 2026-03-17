from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import Order, OrderStatus, Platform
from bot.db.repositories import OrderRepository, PaymentRepository, UserRepository
from bot.services.payment_service import PaymentService
from bot.texts import payment_description


settings = get_settings()


def _platform(value: Platform | str) -> Platform:
    return value if isinstance(value, Platform) else Platform(value)


@dataclass(slots=True)
class PaymentInitiationResult:
    order: Order
    payment_id: str
    payment_url: str
    amount: Decimal


async def create_order_common(
    user_id: int,
    username: str | None,
    text: str,
    character_id: int | None,
    creative_id: int | None,
    platform: Platform | str,
    session: AsyncSession,
) -> Order:
    user = await UserRepository(session).get_or_create_user(user_id, username, _platform(platform))
    order_repo = OrderRepository(session)
    order = await order_repo.create_order(user.id, text, Decimal(settings.order_price), _platform(platform))
    if character_id and creative_id:
        await order_repo.update_order_selection(order.id, character_id, creative_id)
        order = await order_repo.get_order(order.id) or order
    return order


async def initiate_payment_common(order_id: int, session: AsyncSession) -> PaymentInitiationResult:
    amount = Decimal(settings.order_price)
    payment_service = PaymentService()
    payment_id, payment_url = await payment_service.create_payment(
        order_id=order_id,
        amount=amount,
        description=payment_description(order_id),
        return_url=settings.webhook_host,
    )
    await PaymentRepository(session).create_payment(order_id, payment_id, amount)
    await OrderRepository(session).set_payment_reference(order_id, payment_id)
    await OrderRepository(session).set_status(order_id, OrderStatus.pending_payment)
    order = await OrderRepository(session).get_order(order_id)
    if not order:
        raise ValueError("Order not found")
    return PaymentInitiationResult(order=order, payment_id=payment_id, payment_url=payment_url, amount=amount)


async def handle_payment_success_common(order_id: int, session: AsyncSession) -> Order | None:
    order_repo = OrderRepository(session)
    order = await order_repo.get_order(order_id)
    if not order or not order.payment_id:
        return order
    await order_repo.mark_paid(order_id, order.payment_id)
    return await order_repo.get_order(order_id)
