from vkbottle import API, Bot

from bot.config import get_settings


def build_vk_bot() -> Bot:
    settings = get_settings()
    api = API(settings.vk_bot_token)
    return Bot(api=api)
