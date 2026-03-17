from vkbottle import BaseStateGroup
from vkbottle.bot import Message

from bot.vk.runtime import get_vk_bot


class VkUserState(BaseStateGroup):
    waiting_text_choice = "waiting_text_choice"
    waiting_own_text = "waiting_own_text"
    waiting_recipient_name = "waiting_recipient_name"
    waiting_occasion = "waiting_occasion"
    waiting_details = "waiting_details"
    waiting_text_approval = "waiting_text_approval"
    browsing_characters = "browsing_characters"
    browsing_creatives = "browsing_creatives"
    confirming_order = "confirming_order"
    waiting_payment = "waiting_payment"


def get_state_payload(message: Message) -> dict:
    if not message.state_peer or not message.state_peer.payload:
        return {}
    return dict(message.state_peer.payload)


def get_state_name(message: Message) -> str | None:
    return message.state_peer.state if message.state_peer else None


def is_state(message: Message, state: str) -> bool:
    return get_state_name(message) == state


async def set_state(peer_id: int, state: str, **payload: object) -> None:
    await get_vk_bot().state_dispenser.set(peer_id, state, **payload)


async def update_state(message: Message, state: str | None = None, **updates: object) -> None:
    payload = get_state_payload(message)
    payload.update(updates)
    target_state = state or get_state_name(message)
    if target_state is None:
        raise RuntimeError("Cannot update VK state without current state")
    await set_state(message.peer_id, target_state, **payload)


async def clear_state(peer_id: int) -> None:
    await get_vk_bot().state_dispenser.delete(peer_id)
