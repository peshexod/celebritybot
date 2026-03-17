from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import Character, CharacterCreative, Order
from bot.db.repositories import CharacterRepository, OrderRepository


@dataclass(slots=True)
class CharacterPageResult:
    character: Character
    preview_creative: CharacterCreative | None
    preview_source: str
    total: int
    page: int


@dataclass(slots=True)
class CreativePageResult:
    creative: CharacterCreative
    total: int
    page: int


@dataclass(slots=True)
class OrderSelectionResult:
    order: Order
    character: Character | None
    creative: CharacterCreative | None


async def start_browsing_common(user_id: int, page: int, session: AsyncSession) -> CharacterPageResult | None:
    del user_id
    return await get_characters_page_common(page, session)


async def get_characters_page_common(page: int, session: AsyncSession) -> CharacterPageResult | None:
    character_repo = CharacterRepository(session)
    total_characters = await character_repo.count_characters()
    if total_characters == 0:
        return None

    normalized_page = page % total_characters
    characters = await character_repo.list_characters(page=normalized_page, page_size=1)
    if not characters:
        return None

    character = characters[0]
    creatives = await character_repo.list_creatives(character.id, page=0)
    first_creative = creatives[0] if creatives else None
    preview_source = first_creative.image_path if first_creative else character.preview_image_path
    return CharacterPageResult(
        character=character,
        preview_creative=first_creative,
        preview_source=preview_source,
        total=total_characters,
        page=normalized_page,
    )


async def get_creatives_page_common(character_id: int, page: int, session: AsyncSession) -> CreativePageResult | None:
    character_repo = CharacterRepository(session)
    total_creatives = await character_repo.count_creatives(character_id)
    if total_creatives == 0:
        return None

    normalized_page = page % total_creatives
    creatives = await character_repo.list_creatives(character_id, page=normalized_page)
    if not creatives:
        return None

    return CreativePageResult(creative=creatives[0], total=total_creatives, page=normalized_page)


async def select_character_common(character_id: int, session: AsyncSession) -> CreativePageResult | None:
    return await get_creatives_page_common(character_id, page=0, session=session)


async def select_creative_common(
    order_id: int,
    character_id: int,
    creative_id: int,
    session: AsyncSession,
) -> OrderSelectionResult | None:
    order_repo = OrderRepository(session)
    character_repo = CharacterRepository(session)
    await order_repo.update_order_selection(order_id, character_id, creative_id)
    order = await order_repo.get_order(order_id)
    if not order:
        return None
    character = await character_repo.get_character(character_id)
    creative = await character_repo.get_creative(creative_id)
    return OrderSelectionResult(order=order, character=character, creative=creative)
