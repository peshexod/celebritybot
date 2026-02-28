from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_mode: str = Field(default="polling", alias="BOT_MODE")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    vk_bot_token: str = Field(default="", alias="VK_BOT_TOKEN")
    vk_group_id: int = Field(default=0, alias="VK_GROUP_ID")

    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@db:5432/celebrity_bot", alias="DATABASE_URL")

    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    runpod_api_key: str = Field(default="", alias="RUNPOD_API_KEY")
    runpod_endpoint: str = Field(default="", alias="RUNPOD_ENDPOINT")

    yookassa_shop_id: str = Field(default="", alias="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field(default="", alias="YOOKASSA_SECRET_KEY")

    webhook_host: str = Field(default="http://localhost:8080", alias="WEBHOOK_HOST")
    webhook_path: str = Field(default="/webhook/telegram", alias="WEBHOOK_PATH")

    order_price: int = Field(default=299, alias="ORDER_PRICE")
    max_text_length: int = Field(default=500, alias="MAX_TEXT_LENGTH")
    max_regen_attempts: int = Field(default=5, alias="MAX_REGEN_ATTEMPTS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
