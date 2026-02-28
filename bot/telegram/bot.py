from aiogram import Bot, Dispatcher

from bot.config import get_settings
from bot.telegram.handlers import character, greeting, orders, payment, start
from bot.telegram.middlewares import DBSessionMiddleware


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.update.middleware(DBSessionMiddleware())
    dp.include_router(start.router)
    dp.include_router(greeting.router)
    dp.include_router(character.router)
    dp.include_router(payment.router)
    dp.include_router(orders.router)
    return dp


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(token=settings.telegram_bot_token)
