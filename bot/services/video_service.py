import aiohttp
import logging

from bot.config import get_settings

logger = logging.getLogger(__name__)


class VideoService:
    """Service for submitting video generation jobs to RunPod (Sonic)"""

    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.settings = get_settings()

    async def submit_job(
        self,
        user_id: str,
        bot_token: str,
        creative_image_base64: str,
        audio_base64: str,
        webhook_url: str | None = None,
        image_filename: str = "image.png",
        audio_filename: str = "voice.mp3",
    ) -> str:
        """
        Submit a video generation job to RunPod.

        Args:
            user_id: Telegram/VK user ID for notifications
            bot_token: Bot token for sending messages
            creative_image_base64: Base64-encoded image
            audio_base64: Base64-encoded audio
            webhook_url: Optional webhook URL for async completion notification
            image_filename: Filename for the image
            audio_filename: Filename for the audio

        Returns:
            Job ID from RunPod
        """
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
            },
        }

        # Add webhook if provided
        if webhook_url:
            payload["webhook"] = {
                "url": webhook_url,
                "events": ["completed", "failed"],
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.settings.runpod_endpoint, headers=headers, json=payload, timeout=60) as resp:
                resp.raise_for_status()
                data = await resp.json()

        job_id = data.get("id", "")
        logger.info("Submitted Sonic video job: id=%s user_id=%s", job_id, user_id)
        return job_id

    async def get_job_status(self, job_id: str) -> str:
        """Get job status from RunPod"""
        status_url = self.settings.runpod_endpoint.replace("/run", f"/status/{job_id}")
        headers = {"Authorization": f"Bearer {self.settings.runpod_api_key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(status_url, headers=headers, timeout=30) as resp:
                resp.raise_for_status()
                data = await resp.json()
        return data.get("status", "UNKNOWN")

    def should_retry(self, attempt: int) -> bool:
        """Check if we should retry based on attempt number"""
        return attempt < self.MAX_ATTEMPTS
