import aiohttp

from bot.config import get_settings


class VideoService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def submit_job(
        self,
        user_id: str,
        bot_token: str,
        creative_image_base64: str,
        audio_base64: str,
        image_filename: str = "image.png",
        audio_filename: str = "voice.mp3",
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.runpod_api_key}",
        }
        payload = {
            "input": {
                "user_id": user_id,
                "bot_token": bot_token,
                "image_input": {"base64": creative_image_base64, "filename": image_filename},
                "audio_input": {"base64": audio_base64, "filename": audio_filename},
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.settings.runpod_endpoint, headers=headers, json=payload, timeout=60) as resp:
                resp.raise_for_status()
                data = await resp.json()
        return data.get("id", "")

    async def get_job_status(self, job_id: str) -> str:
        status_url = self.settings.runpod_endpoint.replace("/run", f"/status/{job_id}")
        headers = {"Authorization": f"Bearer {self.settings.runpod_api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(status_url, headers=headers, timeout=30) as resp:
                resp.raise_for_status()
                data = await resp.json()
        return data.get("status", "UNKNOWN")
