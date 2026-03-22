"""Chatterbox TTS service for async job submission via RunPod with webhook callback."""

import logging

import aiohttp

from bot.config import get_settings

logger = logging.getLogger(__name__)


class ChatterboxService:
    """Service for submitting Chatterbox TTS jobs to RunPod with webhook callback.

    Voice cloning is performed by passing ``reference_audio_url`` directly to RunPod.
    The URL points to the bot's own static file server (``/media/voices/``), which
    is accessible from RunPod since both run in the same network.

    For standalone scripts (e.g. ``generate_video.py``) where the bot's static
    server is not accessible, the caller is responsible for uploading the voice
    sample to S3 (or any public URL) and passing that pre-built URL here.
    """

    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.settings = get_settings()

    async def submit_job(
        self,
        text: str,
        reference_audio_url: str,
        webhook_url: str,
    ) -> str:
        """
        Submit a Chatterbox TTS job to RunPod.

        The ``reference_audio_url`` is passed directly to RunPod as the voice
        sample URL for cloning. It must be a publicly accessible URL (e.g.
        ``http://bot-server:8080/media/voices/trump.wav`` or an S3 presigned URL).

        Args:
            text: Text to synthesize.
            reference_audio_url: Publicly accessible URL of the voice sample WAV file.
            webhook_url: URL to call when the job completes.

        Returns:
            Job ID from RunPod.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.runpod_api_key}",
        }

        payload = {
            "input": {
                "text": text,
                "reference_audio_url": reference_audio_url,
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
        logger.info(
            "Submitted Chatterbox job: id=%s text=%s reference_audio_url=%s",
            job_id,
            text[:50],
            reference_audio_url,
        )
        return job_id

    async def get_job_status(self, job_id: str) -> dict:
        """Get job status from RunPod (for debugging/monitoring)."""
        status_url = self.settings.runpod_chatterbox_endpoint.replace("/run", f"/status/{job_id}")
        headers = {"Authorization": f"Bearer {self.settings.runpod_api_key}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(status_url, headers=headers, timeout=30) as resp:
                resp.raise_for_status()
                return await resp.json()

    def should_retry(self, attempt: int) -> bool:
        """Check if we should retry based on attempt number."""
        return attempt < self.MAX_ATTEMPTS
