from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

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


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="create_present", description="Создать поздарвление"),
            BotCommand(command="continue_order", description="Продолжить заказ"),
            BotCommand(command="my_orders", description="Мои заказы"),
            BotCommand(command="help", description="Помощь"),
        ]
    )
