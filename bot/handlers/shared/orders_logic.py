from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Order, Platform
from bot.db.repositories import OrderRepository, UserRepository


def _platform(value: Platform | str) -> Platform:
    return value if isinstance(value, Platform) else Platform(value)


async def get_user_orders_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    session: AsyncSession,
    page: int = 0,
    page_size: int = 5,
) -> list[Order]:
    user = await UserRepository(session).get_or_create_user(user_id, username, _platform(platform))
    return await OrderRepository(session).list_user_orders(user.id, page=page, page_size=page_size)


async def get_order_details_common(order_id: int, session: AsyncSession) -> Order | None:
    return await OrderRepository(session).get_order(order_id)


async def get_user_order_details_common(
    user_id: int,
    username: str | None,
    platform: Platform | str,
    order_id: int,
    session: AsyncSession,
) -> Order | None:
    user = await UserRepository(session).get_or_create_user(user_id, username, _platform(platform))
    order = await OrderRepository(session).get_order(order_id)
    if not order or order.user_id != user.id:
        return None
    return order
