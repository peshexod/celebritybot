from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle.bot import Message

from bot.config import get_settings
from bot.handlers.shared import (
    get_characters_page_common,
    get_creatives_page_common,
    handle_resume_order_common,
    select_character_common,
    select_creative_common,
)
from bot.handlers.vk import labeler
from bot.texts import (
    CHARACTER_RESTORE_FAILED_TEXT,
    CONTINUE_CHARACTER_CHOICE_TEXT,
    NO_CREATIVES_TEXT,
    NO_MORE_CHARACTERS_TEXT,
    NO_MORE_CREATIVES_TEXT,
    ORDER_CONTEXT_LOST_TEXT,
    character_caption,
    change_text_prompt,
    creative_caption,
    order_confirmation_text,
)
from bot.vk.helpers import answer_message, extract_payload, payload_command, send_photo_message
from bot.vk.keyboards import characters_keyboard_vk, creative_keyboard_vk, order_confirm_keyboard_vk
from bot.vk.states import VkUserState, get_state_payload, get_state_name, set_state


settings = get_settings()


async def send_character_card_vk(message: Message, session: AsyncSession, page: int) -> int | None:
    result = await get_characters_page_common(page=page, session=session)
    if not result:
        await answer_message(message, NO_MORE_CHARACTERS_TEXT)
        return None

    await send_photo_message(
        message,
        photo_source=result.preview_source,
        text=character_caption(result.character.name, result.character.description, result.page, result.total),
        keyboard=characters_keyboard_vk(result.character, result.page),
    )
    return result.page


async def send_creative_card_vk(message: Message, character_id: int, session: AsyncSession, page: int) -> int | None:
    result = await get_creatives_page_common(character_id=character_id, page=page, session=session)
    if not result:
        await answer_message(message, NO_CREATIVES_TEXT)
        return None

    await send_photo_message(
        message,
        photo_source=result.creative.image_path,
        text=creative_caption(result.creative.label, result.page, result.total),
        keyboard=creative_keyboard_vk(result.creative.id, result.page),
    )
    return result.page


@labeler.message()
async def character_payload_handler(message: Message, session: AsyncSession) -> None:
    payload = extract_payload(message)
    command = payload.get("cmd")
    state = get_state_name(message)
    data = get_state_payload(message)

    if command == "text_ok" and state == VkUserState.waiting_text_approval:
        page = await send_character_card_vk(message, session, page=0)
        if page is None:
            return
        await set_state(message.peer_id, VkUserState.browsing_characters, **data, character_page=page)
        return

    if command == "text_ok" and state is None:
        result = await handle_resume_order_common(message.from_id, None, "vk", session)
        if result.kind in {"missing", "unavailable"}:
            await answer_message(message, ORDER_CONTEXT_LOST_TEXT)
            return
        page = await send_character_card_vk(message, session, page=0)
        if page is None:
            return
        await set_state(
            message.peer_id,
            VkUserState.browsing_characters,
            order_id=result.order_id,
            final_text=result.text or "",
            character_page=page,
        )
        await answer_message(message, CONTINUE_CHARACTER_CHOICE_TEXT)
        return

    if command == "char_page" and state == VkUserState.browsing_characters:
        page = await send_character_card_vk(message, session, page=int(payload.get("page", 0)))
        if page is None:
            return
        await set_state(message.peer_id, VkUserState.browsing_characters, **data, character_page=page)
        return

    if command == "char" and state == VkUserState.browsing_characters:
        character_id = int(payload["character_id"])
        result = await select_character_common(character_id, session)
        if not result:
            await answer_message(message, NO_CREATIVES_TEXT)
            return
        page = await send_creative_card_vk(message, character_id=character_id, session=session, page=result.page)
        if page is None:
            return
        await set_state(
            message.peer_id,
            VkUserState.browsing_creatives,
            **data,
            character_id=character_id,
            creative_page=page,
        )
        return

    if command == "creative_page" and state == VkUserState.browsing_creatives:
        page = await send_creative_card_vk(
            message,
            character_id=int(data["character_id"]),
            session=session,
            page=int(payload.get("page", 0)),
        )
        if page is None:
            await answer_message(message, NO_MORE_CREATIVES_TEXT)
            return
        await set_state(message.peer_id, VkUserState.browsing_creatives, **data, creative_page=page)
        return

    if command == "change_character" and state in {VkUserState.browsing_creatives, VkUserState.confirming_order}:
        page = await send_character_card_vk(message, session, page=0)
        if page is None:
            return
        await set_state(message.peer_id, VkUserState.browsing_characters, **data, character_page=page)
        return

    if command == "change_creative" and state == VkUserState.confirming_order:
        character_id = data.get("character_id")
        if not character_id:
            await answer_message(message, CHARACTER_RESTORE_FAILED_TEXT)
            return
        page = await send_creative_card_vk(
            message,
            character_id=int(character_id),
            session=session,
            page=int(data.get("creative_page", 0)),
        )
        if page is None:
            return
        await set_state(message.peer_id, VkUserState.browsing_creatives, **data, creative_page=page)
        return

    if command == "change_text" and state == VkUserState.confirming_order:
        await set_state(message.peer_id, VkUserState.waiting_own_text, **data)
        await answer_message(message, change_text_prompt(settings.max_text_length))
        return

    if command == "creative" and state == VkUserState.browsing_creatives:
        creative_id = int(payload["creative_id"])
        result = await select_creative_common(
            order_id=int(data["order_id"]),
            character_id=int(data["character_id"]),
            creative_id=creative_id,
            session=session,
        )
        if not result:
            await answer_message(message, NO_CREATIVES_TEXT)
            return
        await set_state(message.peer_id, VkUserState.confirming_order, **data, creative_id=creative_id)
        await answer_message(
            message,
            order_confirmation_text(
                text=str(data.get("final_text", "")),
                character=result.character.name if result.character else str(data["character_id"]),
                creative=result.creative.label or f"Образ #{creative_id}" if result.creative else str(creative_id),
            ),
            keyboard=order_confirm_keyboard_vk(),
        )
