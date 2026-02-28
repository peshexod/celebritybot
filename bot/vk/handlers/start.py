from vkbottle.bot import Message


async def start_handler(message: Message) -> None:
    if message.text == "/start":
        await message.answer("Привет! Это VK-версия бота. Создание поздравлений будет доступно в этом интерфейсе.")
