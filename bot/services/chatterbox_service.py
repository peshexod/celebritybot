"""Chatterbox TTS service for async job submission via RunPod"""

import aiohttp
import logging

from bot.config import get_settings

logger = logging.getLogger(__name__)


class ChatterboxService:
    """Service for submitting Chatterbox TTS jobs to RunPod with webhook callback"""

    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.settings = get_settings()

    async def submit_job(
        self,
        text: str,
        voice_name: str,
        webhook_url: str,
    ) -> str:
        """
        Submit a Chatterbox TTS job to RunPod.

        Args:
            text: Text to synthesize
            voice_name: Name of the voice to use
            webhook_url: URL to call when job completes

        Returns:
            Job ID from RunPod
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.runpod_api_key}",
        }

        payload = {
            "input": {
                "text": text,
                "voice_name": voice_name,
            },
            "webhook": {
                "url": webhook_url,
                "events": ["completed", "failed"],
            },
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.settings.runpod_chatterbox_endpoint,
                headers=headers,
                json=payload,
                timeout=60,
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        job_id = data.get("id", "")
        logger.info("Submitted Chatterbox job: id=%s text=%s voice=%s", job_id, text[:50], voice_name)
        return job_id

    async def get_job_status(self, job_id: str) -> dict:
        """Get job status from RunPod (for debugging/monitoring)"""
        status_url = self.settings.runpod_chatterbox_endpoint.replace("/run", f"/status/{job_id}")
        headers = {"Authorization": f"Bearer {self.settings.runpod_api_key}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(status_url, headers=headers, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.json()

    def should_retry(self, attempt: int) -> bool:
        """Check if we should retry based on attempt number"""
        return attempt < self.MAX_ATTEMPTS
