from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db.models import Character, CharacterCreative, Order, OrderStatus, Payment, PaymentStatus, Platform, User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_telegram_user(self, telegram_id: int, username: str | None = None) -> User:
        query: Select[tuple[User]] = select(User).where(User.telegram_id == telegram_id)
        user = await self.session.scalar(query)
        if user:
            if username and user.username != username:
                user.username = username
                await self.session.commit()
            return user
        user = User(telegram_id=telegram_id, username=username)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user


class CharacterRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_characters(self, page: int = 0, page_size: int = 3) -> list[Character]:
        query = (
            select(Character)
            .where(Character.is_active.is_(True))
            .order_by(Character.sort_order.asc(), Character.id.asc())
            .offset(page * page_size)
            .limit(page_size)
        )
        result = await self.session.scalars(query)
        return list(result)

    async def get_character(self, character_id: int) -> Character | None:
        return await self.session.get(Character, character_id)

    async def count_characters(self) -> int:
        query = select(func.count(Character.id)).where(Character.is_active.is_(True))
        count = await self.session.scalar(query)
        return int(count or 0)

    async def list_creatives(self, character_id: int, page: int = 0, page_size: int = 1) -> list[CharacterCreative]:
        query = (
            select(CharacterCreative)
            .where(and_(CharacterCreative.character_id == character_id, CharacterCreative.is_active.is_(True)))
            .order_by(CharacterCreative.sort_order.asc(), CharacterCreative.id.asc())
            .offset(page * page_size)
            .limit(page_size)
        )
        result = await self.session.scalars(query)
        return list(result)

    async def get_creative(self, creative_id: int) -> CharacterCreative | None:
        return await self.session.get(CharacterCreative, creative_id)

    async def count_creatives(self, character_id: int) -> int:
        query = select(func.count(CharacterCreative.id)).where(
            and_(CharacterCreative.character_id == character_id, CharacterCreative.is_active.is_(True))
        )
        count = await self.session.scalar(query)
        return int(count or 0)

    async def set_creative_telegram_file_id(self, creative_id: int, telegram_file_id: str) -> None:
        creative = await self.session.get(CharacterCreative, creative_id)
        if not creative:
            return
        creative.telegram_file_id = telegram_file_id
        await self.session.commit()


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_order(self, user_id: int, text: str, price: Decimal, platform: Platform) -> Order:
        order = Order(user_id=user_id, text=text, price=price, platform=platform)
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def get_order(self, order_id: int) -> Order | None:
        return await self.session.get(Order, order_id)

    async def get_order_with_user(self, order_id: int) -> Order | None:
        query = select(Order).options(selectinload(Order.user)).where(Order.id == order_id)
        return await self.session.scalar(query)

    async def update_order_selection(self, order_id: int, character_id: int, creative_id: int) -> None:
        order = await self.session.get(Order, order_id)
        if not order:
            return
        order.character_id = character_id
        order.creative_id = creative_id
        order.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()

    async def mark_paid(self, order_id: int, payment_id: str) -> None:
        order = await self.session.get(Order, order_id)
        if not order:
            return
        order.status = OrderStatus.paid
        order.payment_id = payment_id
        order.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()

    async def set_payment_reference(self, order_id: int, payment_id: str) -> None:
        order = await self.session.get(Order, order_id)
        if not order:
            return
        order.payment_id = payment_id
        order.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()

    async def update_order_text(self, order_id: int, text: str) -> None:
        order = await self.session.get(Order, order_id)
        if not order:
            return
        order.text = text
        order.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()

    async def set_status(self, order_id: int, status: OrderStatus, error_message: str | None = None) -> None:
        order = await self.session.get(Order, order_id)
        if not order:
            return
        order.status = status
        order.error_message = error_message
        order.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()

    async def set_runpod_job(self, order_id: int, job_id: str) -> None:
        order = await self.session.get(Order, order_id)
        if not order:
            return
        order.runpod_job_id = job_id
        order.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()

    async def increment_attempt(self, order_id: int, error_message: str) -> None:
        order = await self.session.get(Order, order_id)
        if not order:
            return
        order.attempt_number += 1
        order.status = OrderStatus.retrying
        order.error_message = error_message
        order.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.session.commit()

    async def list_user_orders(self, user_id: int, page: int = 0, page_size: int = 5) -> list[Order]:
        query = (
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .offset(page * page_size)
            .limit(page_size)
        )
        result = await self.session.scalars(query)
        return list(result)

    async def get_latest_user_order(self, user_id: int) -> Order | None:
        query = (
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(query)

    async def list_stuck_orders(self, older_than_minutes: int = 15) -> list[Order]:
        threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=older_than_minutes)
        query = select(Order).where(
            and_(Order.status == OrderStatus.generating_video, Order.updated_at < threshold)
        )
        result = await self.session.scalars(query)
        return list(result)


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_payment(self, order_id: int, yookassa_payment_id: str, amount: Decimal) -> Payment:
        payment = Payment(order_id=order_id, yookassa_payment_id=yookassa_payment_id, amount=amount)
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def set_status(self, yookassa_payment_id: str, status: PaymentStatus, refund_id: str | None = None) -> Payment | None:
        payment = await self.session.scalar(select(Payment).where(Payment.yookassa_payment_id == yookassa_payment_id))
        if not payment:
            return None
        payment.status = status
        if status == PaymentStatus.refunded:
            payment.refunded_at = datetime.now(UTC).replace(tzinfo=None)
            payment.refund_id = refund_id
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_by_external_id(self, yookassa_payment_id: str) -> Payment | None:
        return await self.session.scalar(select(Payment).where(Payment.yookassa_payment_id == yookassa_payment_id))

    async def list_pending(self, limit: int = 50) -> list[Payment]:
        query = (
            select(Payment)
            .where(Payment.status == PaymentStatus.pending)
            .order_by(Payment.created_at.asc())
            .limit(limit)
        )
        result = await self.session.scalars(query)
        return list(result)
