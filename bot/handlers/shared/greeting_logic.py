from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import Order, Platform, User
from bot.db.repositories import OrderRepository, UserRepository
from bot.services.ai_service import AIService


settings = get_settings()
ai_service = AIService()


class TextTooLongError(ValueError):
    pass


@dataclass(slots=True)
class TextChoiceResult:
    mode: str


@dataclass(slots=True)
class TextResult:
    order: Order
    text: str
    user: User


def _platform(value: Platform | str) -> Platform:
    return value if isinstance(value, Platform) else Platform(value)


async def handle_greeting_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    session: AsyncSession,
) -> User:
    return await UserRepository(session).get_or_create_user(user_id, username, _platform(platform))


async def handle_choose_ai_text_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    session: AsyncSession,
) -> TextChoiceResult:
    await handle_greeting_common(user_id, username, platform, session)
    return TextChoiceResult(mode="ai")


async def handle_choose_own_text_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    session: AsyncSession,
) -> TextChoiceResult:
    await handle_greeting_common(user_id, username, platform, session)
    return TextChoiceResult(mode="own")


async def save_own_text_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    text: str,
    session: AsyncSession,
    existing_order_id: int | None = None,
) -> TextResult:
    normalized_text = (text or "").strip()
    if len(normalized_text) > settings.max_text_length:
        raise TextTooLongError(settings.max_text_length)

    user = await handle_greeting_common(user_id, username, platform, session)
    order_repo = OrderRepository(session)
    if existing_order_id:
        await order_repo.update_order_text(existing_order_id, normalized_text)
        order = await order_repo.get_order(existing_order_id)
    else:
        order = await order_repo.create_order(user.id, normalized_text, Decimal(settings.order_price), _platform(platform))

    if not order:
        raise ValueError("Order was not created")

    return TextResult(order=order, text=normalized_text, user=user)


async def handle_ai_generation_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    recipient_name: str,
    occasion: str,
    details: str,
    session: AsyncSession,
    existing_order_id: int | None = None,
) -> TextResult:
    generated_text = await ai_service.generate_greeting(recipient_name, occasion, details)
    return await save_own_text_common(
        user_id=user_id,
        username=username,
        platform=platform,
        text=generated_text,
        session=session,
        existing_order_id=existing_order_id,
    )


async def regenerate_ai_text_common(
    order_id: int,
    recipient_name: str,
    occasion: str,
    details: str,
    session: AsyncSession,
) -> str:
    text = await ai_service.generate_greeting(recipient_name, occasion, details)
    await OrderRepository(session).update_order_text(order_id, text)
    return text
