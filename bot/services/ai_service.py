import aiohttp

from bot.config import get_settings


class AIService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    async def generate_greeting(self, recipient_name: str, occasion: str, details: str | None = None) -> str:
        prompt = (
            "Сгенерируй короткое поздравление на русском языке, до 100 слов, дружелюбный тон. "
            f"Получатель: {recipient_name}. Повод: {occasion}. "
            f"Детали: {details or 'нет дополнительных деталей'}."
        )
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Ты пишешь краткие поздравления для видео-кружка."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=payload, headers=headers, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
        return data["choices"][0]["message"]["content"].strip()
