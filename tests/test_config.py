from bot.config import Settings


def test_settings_read_from_aliases() -> None:
    settings = Settings(
        BOT_MODE="polling",
        TELEGRAM_BOT_TOKEN="token",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db",
        ORDER_PRICE=499,
        MAX_TEXT_LENGTH=500,
        MAX_REGEN_ATTEMPTS=5,
    )

    assert settings.bot_mode == "polling"
    assert settings.telegram_bot_token == "token"
    assert settings.order_price == 499
