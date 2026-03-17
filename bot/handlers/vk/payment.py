from sqlalchemy.ext.asyncio import AsyncSession
from vkbottle.bot import Message

from bot.handlers.shared import initiate_payment_common
from bot.handlers.vk import labeler
from bot.services.payment_service import PaymentConfigurationError
from bot.texts import PAYMENT_CONFIGURATION_ERROR_TEXT, PAYMENT_WAITING_TEXT
from bot.vk.helpers import answer_message, payload_command
from bot.vk.keyboards import payment_url_keyboard_vk
from bot.vk.states import VkUserState, get_state_payload, get_state_name, set_state


@labeler.message()
async def payment_handler(message: Message, session: AsyncSession) -> None:
    if payload_command(message) != "pay_order" or get_state_name(message) != VkUserState.confirming_order:
        return

    data = get_state_payload(message)
    try:
        payment = await initiate_payment_common(int(data["order_id"]), session)
    except PaymentConfigurationError:
        await answer_message(message, PAYMENT_CONFIGURATION_ERROR_TEXT)
        return

    await set_state(message.peer_id, VkUserState.waiting_payment, **data)
    await answer_message(message, PAYMENT_WAITING_TEXT, keyboard=payment_url_keyboard_vk(payment.payment_url))
