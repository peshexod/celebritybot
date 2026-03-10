"""Order processing service with async webhook-based flow"""

import asyncio
import base64
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.db.models import OrderStatus
from bot.db.repositories import CharacterRepository, OrderRepository
from bot.services.chatterbox_service import ChatterboxService
from bot.services.video_service import VideoService
from bot.services.voice_service import VoiceService


settings = get_settings()


class OrderService:
    """Service for processing orders using async webhook-based flow"""

    def __init__(self) -> None:
        self.chatterbox_service = ChatterboxService()
        self.video_service = VideoService()

    async def process_paid_order(
        self,
        session: AsyncSession,
        order_id: int,
        user_platform_id: str,
        bot_token: str,
    ) -> None:
        """
        Process a paid order by starting the Chatterbox TTS job.
        Video generation will happen via webhook callback.
        """
        order_repo = OrderRepository(session)
        character_repo = CharacterRepository(session)

        order = await order_repo.get_order(order_id)
        if not order or not order.character_id or not order.creative_id:
            await order_repo.set_status(order_id, OrderStatus.failed, "Order missing character or creative")
            return

        character = await character_repo.get_character(order.character_id)
        if not character:
            await order_repo.set_status(order_id, OrderStatus.failed, "Character not found")
            return

        # Build webhook URL
        webhook_url = f"{settings.webhook_host.rstrip('/')}/webhook/chatterbox"

        # Submit Chatterbox TTS job
        try:
            job_id = await self.chatterbox_service.submit_job(
                text=order.text,
                voice_name=character.name,  # Using character name as voice identifier
                webhook_url=webhook_url,
            )
            await order_repo.set_chatterbox_job(order_id, job_id)
        except Exception as exc:
            await order_repo.set_status(order_id, OrderStatus.failed, f"Failed to submit Chatterbox job: {exc}")
            raise

    async def retry_chatterbox(
        self,
        session: AsyncSession,
        order_id: int,
        user_platform_id: str,
        bot_token: str,
    ) -> bool:
        """
        Retry the Chatterbox TTS job for an order.

        Returns True if retry was submitted, False if max attempts reached.
        """
        order_repo = OrderRepository(session)
        character_repo = CharacterRepository(session)

        order = await order_repo.get_order(order_id)
        if not order:
            return False

        if not self.chatterbox_service.should_retry(order.chatterbox_attempt):
            await order_repo.set_status(order_id, OrderStatus.failed, "Max Chatterbox attempts reached")
            return False

        character = await character_repo.get_character(order.character_id) if order.character_id else None
        if not character:
            return False

        webhook_url = f"{settings.webhook_host.rstrip('/')}/webhook/chatterbox"

        try:
            job_id = await self.chatterbox_service.submit_job(
                text=order.text,
                voice_name=character.name,
                webhook_url=webhook_url,
            )
            await order_repo.set_chatterbox_job(order_id, job_id)
            return True
        except Exception as exc:
            await order_repo.increment_chatterbox_attempt(order_id, str(exc))
            return False


# -------------------------------------------------------------------------
# Legacy sync processing (kept for backward compatibility with old flow)
# -------------------------------------------------------------------------

logger = logging.getLogger(__name__)


class OrderServiceLegacy:
    """Legacy order processing with synchronous calls (kept for reference)"""

    def __init__(self, voice_service: VoiceService, video_service: VideoService) -> None:
        self.voice_service = voice_service
        self.video_service = video_service

    async def process_paid_order(self, session: AsyncSession, order_id: int, user_platform_id: str, bot_token: str) -> None:
        """Synchronous processing - kept for backward compatibility"""
        order_repo = OrderRepository(session)
        character_repo = CharacterRepository(session)
        order = await order_repo.get_order(order_id)
        if not order or not order.character_id or not order.creative_id:
            return

        delays = [5, 15, 45]
        for index, delay in enumerate(delays, start=1):
            try:
                await order_repo.set_status(order_id, OrderStatus.generating_audio)
                character = await character_repo.get_character(order.character_id)
                creative = await character_repo.get_creative(order.creative_id)
                if not character or not creative:
                    raise ValueError("Character or creative not found")

                audio_bytes = await self.voice_service.generate_audio(order.text, character.elevenlabs_voice_id)

                image_bytes = Path(creative.image_path).read_bytes()
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

                await order_repo.set_status(order_id, OrderStatus.generating_video)
                job_id = await self.video_service.submit_job(
                    user_id=user_platform_id,
                    bot_token=bot_token,
                    creative_image_base64=image_base64,
                    audio_base64=audio_base64,
                )
                await order_repo.set_runpod_job(order_id, job_id)
                return
            except Exception as exc:
                await order_repo.increment_attempt(order_id, str(exc))
                if index < len(delays):
                    await asyncio.sleep(delay)

        await order_repo.set_status(order_id, OrderStatus.failed, "Retries exhausted")
