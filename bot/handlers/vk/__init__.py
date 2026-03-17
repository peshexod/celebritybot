from vkbottle.bot import BotLabeler


labeler = BotLabeler()


from bot.handlers.vk import character, greeting, orders, payment, start  # noqa: E402,F401


__all__ = ["labeler", "start", "greeting", "character", "payment", "orders"]
