from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle.bot import Message

from bot.handlers.shared import handle_resume_order_common, handle_start_common
from bot.handlers.vk import labeler
from bot.texts import GREETING_TEXT, HELP_TEXT, NO_ACTIVE_ORDER_TEXT, order_processed_text, resumed_order_text
from bot.vk.helpers import answer_message, payload_command
from bot.vk.keyboards import main_menu_keyboard_vk, order_confirm_keyboard_vk
from bot.vk.states import clear_state, set_state, VkUserState


START_COMMANDS = {"/start", "start", "начать"}


@labeler.message()
async def start_handler(message: Message, session: AsyncSession) -> None:
    text = (message.text or "").strip().lower()
    command = payload_command(message)

    if text in START_COMMANDS:
        await handle_start_common(message.from_id, None, "vk", session)
        await clear_state(message.peer_id)
        await answer_message(message, GREETING_TEXT, keyboard=main_menu_keyboard_vk())
        return

    if command == "help":
        await answer_message(message, HELP_TEXT, keyboard=main_menu_keyboard_vk())
        return

    if command != "resume_order":
        return

    result = await handle_resume_order_common(
        user_id=message.from_id,
        username=None,
        platform="vk",
        session=session,
    )
    if result.kind == "missing":
        await answer_message(message, NO_ACTIVE_ORDER_TEXT, keyboard=main_menu_keyboard_vk())
        return

    if result.kind == "unavailable":
        await answer_message(message, order_processed_text(result.order_id or 0, result.status or "unknown"))
        return

    payload = {"order_id": result.order_id, "final_text": result.text or ""}
    if result.kind == "confirm_ready":
        payload.update({"character_id": result.character_id, "creative_id": result.creative_id})
        await set_state(message.peer_id, VkUserState.confirming_order, **payload)
        await answer_message(
            message,
            resumed_order_text(
                result.text or "",
                result.character_name or str(result.character_id or "-"),
                result.creative_label or str(result.creative_id or "-"),
            ),
            keyboard=order_confirm_keyboard_vk(),
        )
        return

    from bot.handlers.vk.character import send_character_card_vk

    await set_state(message.peer_id, VkUserState.browsing_characters, **payload)
    await send_character_card_vk(message, session, page=0)
