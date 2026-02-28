import asyncio
from decimal import Decimal
from uuid import uuid4

from yookassa import Configuration, Payment, Refund

from bot.config import get_settings


class PaymentService:
    def __init__(self) -> None:
        settings = get_settings()
        Configuration.account_id = settings.yookassa_shop_id
        Configuration.secret_key = settings.yookassa_secret_key

    async def create_payment(self, order_id: int, amount: Decimal, description: str, return_url: str) -> tuple[str, str]:
        payload = {
            "amount": {"value": str(amount), "currency": "RUB"},
            "confirmation": {"type": "redirect", "return_url": return_url},
            "capture": True,
            "description": description,
            "metadata": {"order_id": str(order_id)},
        }
        idempotency_key = str(uuid4())

        payment = await asyncio.to_thread(Payment.create, payload, idempotency_key)
        return payment.id, payment.confirmation.confirmation_url

    async def check_payment(self, payment_id: str) -> str:
        payment = await asyncio.to_thread(Payment.find_one, payment_id)
        return payment.status

    async def create_refund(self, payment_id: str, amount: Decimal) -> str:
        payload = {
            "payment_id": payment_id,
            "amount": {"value": str(amount), "currency": "RUB"},
        }
        refund = await asyncio.to_thread(Refund.create, payload, str(uuid4()))
        return refund.id
