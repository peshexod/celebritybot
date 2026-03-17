from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import OrderStatus, Platform, User
from bot.db.repositories import CharacterRepository, OrderRepository, UserRepository


@dataclass(slots=True)
class ResumeOrderResult:
    kind: str
    order_id: int | None = None
    text: str | None = None
    character_id: int | None = None
    creative_id: int | None = None
    character_name: str | None = None
    creative_label: str | None = None
    status: str | None = None


def _platform(value: Platform | str) -> Platform:
    return value if isinstance(value, Platform) else Platform(value)


async def handle_start_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    session: AsyncSession,
) -> User:
    user_repo = UserRepository(session)
    return await user_repo.get_or_create_user(user_id, username, _platform(platform))


async def handle_resume_order_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    session: AsyncSession,
) -> ResumeOrderResult:
    user = await handle_start_common(user_id, username, platform, session)
    order = await OrderRepository(session).get_latest_user_order(user.id)

    if not order:
        return ResumeOrderResult(kind="missing")

    if order.status != OrderStatus.pending_payment:
        return ResumeOrderResult(kind="unavailable", order_id=order.id, status=order.status.value)

    result = ResumeOrderResult(
        kind="needs_character_selection",
        order_id=order.id,
        text=order.text,
        character_id=order.character_id,
        creative_id=order.creative_id,
        status=order.status.value,
    )

    if not order.character_id or not order.creative_id:
        return result

    character_repo = CharacterRepository(session)
    character = await character_repo.get_character(order.character_id)
    creative = await character_repo.get_creative(order.creative_id)
    result.kind = "confirm_ready"
    result.character_name = character.name if character else str(order.character_id)
    result.creative_label = creative.label or f"Образ #{order.creative_id}" if creative else str(order.creative_id)
    return result
