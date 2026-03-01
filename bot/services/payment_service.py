import asyncio
import logging
from decimal import Decimal
from uuid import uuid4

from yookassa import Configuration, Payment, Refund

from bot.config import get_settings


logger = logging.getLogger(__name__)


class PaymentConfigurationError(ValueError):
    pass


class PaymentService:
    @staticmethod
    def _sanitize_env_value(value: str) -> str:
        return value.strip().strip('"').strip("'")

    @classmethod
    def _validate_credentials(cls, shop_id: str, secret_key: str) -> tuple[str, str]:
        normalized_shop_id = cls._sanitize_env_value(shop_id)
        normalized_secret_key = cls._sanitize_env_value(secret_key)

        if not normalized_shop_id or not normalized_secret_key:
            raise PaymentConfigurationError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY must be set")

        if not normalized_shop_id.isdigit():
            raise PaymentConfigurationError(
                "YOOKASSA_SHOP_ID must be a numeric shop id from YooKassa settings"
            )

        lowered_secret = normalized_secret_key.lower()
        if lowered_secret.startswith("oauth") or normalized_secret_key.startswith("y0_"):
            raise PaymentConfigurationError(
                "YOOKASSA_SECRET_KEY looks like an OAuth token. Use API Secret Key for the shop instead"
            )



        if not (
            normalized_secret_key.startswith("test_")
            or normalized_secret_key.startswith("live_")
        ):
            logger.warning(
                "YOOKASSA_SECRET_KEY has an unexpected prefix. It should usually start with test_ or live_"
            )

        return normalized_shop_id, normalized_secret_key

    def __init__(self) -> None:
        settings = get_settings()
        shop_id, secret_key = self._validate_credentials(
            settings.yookassa_shop_id,
            settings.yookassa_secret_key,
        )
        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key

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
