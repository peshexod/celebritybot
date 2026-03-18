from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle.bot import Message

from bot.config import get_settings
from bot.handlers.shared import (
    TextTooLongError,
    handle_ai_generation_common,
    handle_choose_ai_text_common,
    handle_choose_own_text_common,
    regenerate_ai_text_common,
    save_own_text_common,
)
from bot.handlers.vk import labeler
from bot.texts import (
    DETAILS_PROMPT,
    EDITED_TEXT_PROMPT,
    GENERATING_TEXT,
    MAX_REGEN_ATTEMPTS_TEXT,
    OCCASION_PROMPT,
    RECIPIENT_NAME_PROMPT,
    TEXT_CHOICE_TEXT,
    own_text_prompt,
    text_approval_text,
    text_too_long_text,
)
from bot.vk.helpers import answer_message, extract_payload, payload_command
from bot.vk.keyboards import occasion_keyboard_vk, text_approval_keyboard_vk, text_choice_keyboard_vk
from bot.vk.states import VkUserState, get_state_payload, is_state, set_state


settings = get_settings()


@labeler.message()
async def greeting_payload_handler(message: Message, session: AsyncSession) -> None:
    command = payload_command(message)
    if command == "create_greeting":
        await set_state(message.peer_id, VkUserState.waiting_text_choice)
        await answer_message(message, TEXT_CHOICE_TEXT, keyboard=text_choice_keyboard_vk())
        return

    if command == "own_text" and is_state(message, VkUserState.waiting_text_choice):
        await handle_choose_own_text_common(message.from_id, None, "vk", session)
        await set_state(message.peer_id, VkUserState.waiting_own_text, **get_state_payload(message))
        await answer_message(message, own_text_prompt(settings.max_text_length))
        return

    if command == "ai_text" and is_state(message, VkUserState.waiting_text_choice):
        await handle_choose_ai_text_common(message.from_id, None, "vk", session)
        await set_state(message.peer_id, VkUserState.waiting_recipient_name, regen_attempts=0)
        await answer_message(message, RECIPIENT_NAME_PROMPT)
        return

    if command == "text_retry" and is_state(message, VkUserState.waiting_text_approval):
        payload = get_state_payload(message)
        attempts = int(payload.get("regen_attempts", 0)) + 1
        if attempts >= settings.max_regen_attempts:
            await set_state(message.peer_id, VkUserState.waiting_own_text, **payload)
            await answer_message(message, MAX_REGEN_ATTEMPTS_TEXT)
            return

        text = await regenerate_ai_text_common(
            order_id=int(payload["order_id"]),
            recipient_name=str(payload["recipient_name"]),
            occasion=str(payload["occasion"]),
            details=str(payload.get("details", "")),
            session=session,
        )
        await set_state(
            message.peer_id,
            VkUserState.waiting_text_approval,
            **payload,
            regen_attempts=attempts,
            final_text=text,
        )
        await answer_message(message, text_approval_text(text, regenerated=True), keyboard=text_approval_keyboard_vk())
        return

    if command == "text_edit" and is_state(message, VkUserState.waiting_text_approval):
        await set_state(message.peer_id, VkUserState.waiting_own_text, **get_state_payload(message))
        await answer_message(message, EDITED_TEXT_PROMPT)


@labeler.message(state=VkUserState.waiting_own_text)
async def handle_own_text_message(message: Message, session: AsyncSession) -> None:
    if extract_payload(message):
        return

    payload = get_state_payload(message)
    try:
        result = await save_own_text_common(
            user_id=message.from_id,
            username=None,
            platform="vk",
            text=message.text or "",
            session=session,
            existing_order_id=int(payload["order_id"]) if payload.get("order_id") else None,
        )
    except TextTooLongError:
        await answer_message(message, text_too_long_text(settings.max_text_length))
        return

    await set_state(
        message.peer_id,
        VkUserState.waiting_text_approval,
        **payload,
        order_id=result.order.id,
        final_text=result.text,
    )
    await answer_message(message, text_approval_text(result.text), keyboard=text_approval_keyboard_vk())


@labeler.message(state=VkUserState.waiting_recipient_name)
async def collect_recipient(message: Message) -> None:
    if extract_payload(message):
        return

    await set_state(
        message.peer_id,
        VkUserState.waiting_occasion,
        **get_state_payload(message),
        recipient_name=message.text or "",
    )
    await answer_message(message, OCCASION_PROMPT, keyboard=occasion_keyboard_vk())


@labeler.message(state=VkUserState.waiting_occasion)
async def collect_occasion(message: Message) -> None:
    payload = extract_payload(message)
    occasion = payload.get("value") if payload.get("cmd") == "occasion" else (message.text or "")
    if not occasion:
        return

    await set_state(
        message.peer_id,
        VkUserState.waiting_details,
        **get_state_payload(message),
        occasion=occasion,
    )
    await answer_message(message, DETAILS_PROMPT)


@labeler.message(state=VkUserState.waiting_details)
async def generate_ai_text(message: Message, session: AsyncSession) -> None:
    if extract_payload(message):
        return

    payload = get_state_payload(message)
    details = "" if (message.text or "").lower() == "пропустить" else (message.text or "")
    await answer_message(message, GENERATING_TEXT)
    result = await handle_ai_generation_common(
        user_id=message.from_id,
        username=None,
        platform="vk",
        recipient_name=str(payload["recipient_name"]),
        occasion=str(payload["occasion"]),
        details=details,
        session=session,
        existing_order_id=int(payload["order_id"]) if payload.get("order_id") else None,
    )
    await set_state(
        message.peer_id,
        VkUserState.waiting_text_approval,
        **payload,
        order_id=result.order.id,
        final_text=result.text,
        details=details,
    )
    await answer_message(message, text_approval_text(result.text, ai_generated=True), keyboard=text_approval_keyboard_vk())
