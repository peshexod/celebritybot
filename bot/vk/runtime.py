from vkbottle import PhotoMessageUploader
from vkbottle.bot import Bot


_vk_bot: Bot | None = None
_photo_uploader: PhotoMessageUploader | None = None


def configure_vk_runtime(bot: Bot) -> None:
    global _vk_bot, _photo_uploader
    _vk_bot = bot
    _photo_uploader = PhotoMessageUploader(bot.api)


def get_vk_bot() -> Bot:
    if _vk_bot is None:
        raise RuntimeError("VK bot is not configured")
    return _vk_bot


def get_vk_photo_uploader() -> PhotoMessageUploader:
    if _photo_uploader is None:
        raise RuntimeError("VK photo uploader is not configured")
    return _photo_uploader
