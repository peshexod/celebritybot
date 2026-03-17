import random

import aiohttp
from vkbottle.bot import Message

from bot.vk.runtime import get_vk_bot, get_vk_photo_uploader


def extract_payload(message: Message) -> dict:
    payload = message.get_payload_json()
    return payload if isinstance(payload, dict) else {}


def payload_command(message: Message) -> str | None:
    return extract_payload(message).get("cmd")


async def send_message(peer_id: int, text: str, keyboard: str | None = None, attachment: str | None = None) -> None:
    await get_vk_bot().api.messages.send(
        peer_id=peer_id,
        random_id=random.randint(1, 2_147_483_647),
        message=text,
        keyboard=keyboard,
        attachment=attachment,
    )


async def answer_message(message: Message, text: str, keyboard: str | None = None, attachment: str | None = None) -> None:
    await message.answer(text, keyboard=keyboard, attachment=attachment)


async def _load_remote_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=30) as response:
            response.raise_for_status()
            return await response.read()


async def send_photo_message(message: Message, photo_source: str, text: str, keyboard: str | None = None) -> None:
    uploader = get_vk_photo_uploader()
    if photo_source.startswith(("http://", "https://")):
        file_source: str | bytes = await _load_remote_bytes(photo_source)
    else:
        file_source = photo_source
    attachment = await uploader.upload(file_source=file_source, peer_id=message.peer_id)
    await answer_message(message, text=text, keyboard=keyboard, attachment=attachment)
