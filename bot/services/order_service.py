import asyncio
import base64
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import OrderStatus, PaymentStatus
from bot.db.repositories import CharacterRepository, OrderRepository, PaymentRepository
from bot.services.video_service import VideoService
from bot.services.voice_service import VoiceService


class OrderService:
    def __init__(self, voice_service: VoiceService, video_service: VideoService) -> None:
        self.voice_service = voice_service
        self.video_service = video_service

    async def process_paid_order(self, session: AsyncSession, order_id: int, user_platform_id: str, bot_token: str) -> None:
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

    async def refund_failed_order(self, session: AsyncSession, yookassa_payment_id: str, refund_id: str) -> None:
        payment_repo = PaymentRepository(session)
        payment = await payment_repo.set_status(yookassa_payment_id, PaymentStatus.refunded, refund_id)
        if not payment:
            return
        order_repo = OrderRepository(session)
        await order_repo.set_status(payment.order_id, OrderStatus.refunded)
