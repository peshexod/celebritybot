import base64
import json
import logging
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from bot.config import get_settings
from bot.db.database import SessionLocal
from bot.db.models import OrderStatus, PaymentStatus, Platform
from bot.db.repositories import CharacterRepository, OrderRepository, PaymentRepository
from bot.services.chatterbox_service import ChatterboxService
from bot.services.order_service import OrderService
from bot.services.video_service import VideoService
from bot.services.voice_service import VoiceService


settings = get_settings()
logger = logging.getLogger(__name__)


async def _notify_telegram_order_status(bot: Bot | None, telegram_id: int | None, text: str) -> None:
    if not bot or not telegram_id:
        return
    try:
        await bot.send_message(chat_id=telegram_id, text=text)
    except Exception as exc:
        logger.exception("Failed to send Telegram status update: %s", exc)


def _resolve_platform_target(order) -> tuple[str | None, str]:
    if order.platform == Platform.telegram:
        return str(order.user.telegram_id or ""), settings.telegram_bot_token
    if order.platform == Platform.vk:
        return str(order.user.vk_id or ""), settings.vk_bot_token
    return None, settings.telegram_bot_token


async def _handle_payment_succeeded(session, payment_id: str, payment_order_id: int, telegram_bot: Bot | None = None) -> None:
    payment_repo = PaymentRepository(session)
    order_repo = OrderRepository(session)

    await payment_repo.set_status(payment_id, PaymentStatus.succeeded)
    await order_repo.mark_paid(payment_order_id, payment_id)

    order = await order_repo.get_order_with_user(payment_order_id)
    if not order or not order.user:
        return

    logger.info(
        "YooKassa payment linked: payment_id=%s order_id=%s platform=%s user_id=%s",
        payment_id,
        order.id,
        order.platform,
        order.user.telegram_id if order.platform == Platform.telegram else order.user.vk_id,
    )

    if order.platform == Platform.telegram:
        await _notify_telegram_order_status(
            telegram_bot,
            order.user.telegram_id,
            f"✅ Оплата получена по заказу #{order.id}. Запускаю генерацию.",
        )

    user_platform_id, bot_token = _resolve_platform_target(order)
    if not user_platform_id:
        return

    order_service = OrderService(voice_service=VoiceService(), video_service=VideoService())
    await order_service.process_paid_order(
        session=session,
        order_id=order.id,
        user_platform_id=user_platform_id,
        bot_token=bot_token,
    )

    updated_order = await order_repo.get_order(order.id)
    if not updated_order:
        return

    if order.platform != Platform.telegram:
        return

    if updated_order.status == OrderStatus.generating_video and updated_order.runpod_job_id:
        await _notify_telegram_order_status(
            telegram_bot,
            order.user.telegram_id,
            f"🎬 Генерация видео запущена для заказа #{order.id}.",
        )
    elif updated_order.status in {OrderStatus.retrying, OrderStatus.failed}:
        await _notify_telegram_order_status(
            telegram_bot,
            order.user.telegram_id,
            f"⚠️ По заказу #{order.id} возникла ошибка генерации. Мы пробуем повторно.",
        )


def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def yookassa_webhook(request: web.Request) -> web.Response:
    telegram_bot: Bot | None = request.app.get("telegram_bot")
    payload = await request.json()
    event = payload.get("event", "")
    payment_object = payload.get("object", {})
    payment_id = payment_object.get("id")

    if not payment_id:
        return web.Response(status=400, text="payment id required")

    async with SessionLocal() as session:
        payment_repo = PaymentRepository(session)
        order_repo = OrderRepository(session)
        payment = await payment_repo.get_by_external_id(payment_id)
        if not payment:
            logger.warning("YooKassa webhook payment not found: payment_id=%s event=%s", payment_id, event)
            return web.Response(status=404, text="payment not found")

        if event == "payment.succeeded":
            await _handle_payment_succeeded(session, payment_id, payment.order_id, telegram_bot=telegram_bot)
        elif event == "refund.succeeded":
            refund_id = payment_object.get("refund_id") or payment_object.get("id")
            await payment_repo.set_status(payment_id, PaymentStatus.refunded, refund_id=refund_id)
            await order_repo.set_status(payment.order_id, OrderStatus.refunded)

        logger.info("YooKassa webhook handled: event=%s payment_id=%s order_id=%s", event, payment_id, payment.order_id)

    return web.Response(text="ok")


async def telegram_webhook(request: web.Request) -> web.Response:
    bot: Bot = request.app["telegram_bot"]
    dispatcher: Dispatcher = request.app["telegram_dispatcher"]
    payload = await request.json()
    update = Update.model_validate(payload)
    await dispatcher.feed_update(bot, update)
    return web.Response(text=json.dumps({"ok": True}), content_type="application/json")


# -------------------------------------------------------------------------
# Chatterbox TTS Webhook Handler
# -------------------------------------------------------------------------

async def chatterbox_webhook(request: web.Request) -> web.Response:
    """
    Handle webhook callbacks from RunPod for Chatterbox TTS jobs.

    Expected payload:
    {
        "id": "job_abc123",
        "status": "COMPLETED",
        "output": {
            "audio_base64": "...",
            "error": null
        }
    }
    """
    telegram_bot: Bot | None = request.app.get("telegram_bot")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("Chatterbox webhook: invalid JSON: %s", exc)
        return web.Response(status=400, text="invalid JSON")

    job_id = payload.get("id", "")
    status = payload.get("status", "")
    output = payload.get("output", {})
    error = output.get("error")

    logger.info("Chatterbox webhook: job_id=%s status=%s", job_id, status)

    async with SessionLocal() as session:
        order_repo = OrderRepository(session)
        character_repo = CharacterRepository(session)

        order = await order_repo.get_order_by_chatterbox_job(job_id)
        if not order:
            logger.warning("Chatterbox webhook: order not found for job_id=%s", job_id)
            return web.Response(text="ok")  # Return 200 to not retry

        user_platform_id, bot_token = _resolve_platform_target(order)

        # Handle error case
        if error or status == "FAILED":
            error_msg = str(error) if error else "Unknown error"
            logger.warning("Chatterbox job failed: order_id=%s job_id=%s error=%s", order.id, job_id, error_msg)

            if not ChatterboxService().should_retry(order.chatterbox_attempt):
                # Max attempts reached - fail the order
                await order_repo.set_status(order.id, OrderStatus.failed, f"Chatterbox failed after {order.chatterbox_attempt} attempts: {error_msg}")
                if order.platform == Platform.telegram and order.user and order.user.telegram_id:
                    await _notify_telegram_order_status(
                        telegram_bot,
                        order.user.telegram_id,
                        f"❌ Не удалось сгенерировать аудио для заказа #{order.id} после нескольких попыток.",
                    )
                return web.Response(text="ok")

            # Retry: increment attempt and resubmit
            await order_repo.increment_chatterbox_attempt(order.id, error_msg)

            # Get character voice sample and resubmit
            character = await character_repo.get_character(order.character_id) if order.character_id else None
            if character:
                webhook_url = f"{settings.webhook_host.rstrip('/')}/webhook/chatterbox"
                voice_sample_path = character.voice_sample_path or ""
                reference_audio_url = f"{settings.voice_static_base_url.rstrip('/')}/{voice_sample_path.lstrip('/')}" if voice_sample_path else ""
                chatterbox_service = ChatterboxService()
                try:
                    new_job_id = await chatterbox_service.submit_job(
                        text=order.text,
                        reference_audio_url=reference_audio_url,
                        webhook_url=webhook_url,
                    )
                    await order_repo.set_chatterbox_job(order.id, new_job_id)
                    logger.info("Chatterbox retry submitted: order_id=%s job_id=%s attempt=%s",
                                order.id, new_job_id, order.chatterbox_attempt + 1)
                except Exception as exc:
                    logger.exception("Failed to submit Chatterbox retry: %s", exc)

            return web.Response(text="ok")

        # Success case - start video generation
        audio_base64 = output.get("audio_base64", "")
        if not audio_base64:
            logger.warning("Chatterbox webhook: no audio_base64 in output for job_id=%s", job_id)
            return web.Response(text="ok")

        logger.info("Chatterbox audio generated: order_id=%s job_id=%s", order.id, job_id)

        # Notify user
        if order.platform == Platform.telegram and order.user and order.user.telegram_id:
            await _notify_telegram_order_status(
                telegram_bot,
                order.user.telegram_id,
                "🎤 Аудио готово! Запускаю генерацию видео...",
            )

        # Start video generation
        try:
            await _start_video_generation(session, order, audio_base64, user_platform_id, bot_token, telegram_bot)
        except Exception as exc:
            logger.exception("Failed to start video generation: %s", exc)

    return web.Response(text="ok")


async def _start_video_generation(
    session,
    order,
    audio_base64: str,
    user_platform_id: str,
    bot_token: str,
    telegram_bot: Bot | None = None,
) -> None:
    """Start the video generation (Sonic) job"""
    order_repo = OrderRepository(session)
    character_repo = CharacterRepository(session)

    # Get creative image
    creative = await character_repo.get_creative(order.creative_id) if order.creative_id else None
    if not creative:
        await order_repo.set_status(order.id, OrderStatus.failed, "Creative not found")
        return

    image_bytes = Path(creative.image_path).read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Submit video job with webhook
    webhook_url = f"{settings.webhook_host.rstrip('/')}/webhook/sonic"
    video_service = VideoService()

    job_id = await video_service.submit_job(
        user_id=user_platform_id,
        bot_token=bot_token,
        creative_image_base64=image_base64,
        audio_base64=audio_base64,
        webhook_url=webhook_url,
    )

    await order_repo.set_sonic_job(order.id, job_id)
    logger.info("Sonic video job submitted: order_id=%s job_id=%s", order.id, job_id)


# -------------------------------------------------------------------------
# Sonic Video Webhook Handler
# -------------------------------------------------------------------------

async def sonic_webhook(request: web.Request) -> web.Response:
    """
    Handle webhook callbacks from RunPod for Sonic video jobs.

    Expected payload:
    {
        "id": "job_xyz789",
        "status": "COMPLETED",
        "output": {
            "telegram_file_id": "BAACAgI...",
            "video_url": "https://...",
            "error": null
        }
    }
    """
    telegram_bot: Bot | None = request.app.get("telegram_bot")

    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("Sonic webhook: invalid JSON: %s", exc)
        return web.Response(status=400, text="invalid JSON")

    job_id = payload.get("id", "")
    status = payload.get("status", "")
    output = payload.get("output", {})
    error = output.get("error")

    logger.info("Sonic webhook: job_id=%s status=%s", job_id, status)

    async with SessionLocal() as session:
        order_repo = OrderRepository(session)

        order = await order_repo.get_order_by_sonic_job(job_id)
        if not order:
            logger.warning("Sonic webhook: order not found for job_id=%s", job_id)
            return web.Response(text="ok")  # Return 200 to not retry

        # Handle error case
        if error or status == "FAILED":
            error_msg = str(error) if error else "Unknown error"
            logger.warning("Sonic job failed: order_id=%s job_id=%s error=%s", order.id, job_id, error_msg)

            if not VideoService().should_retry(order.sonic_attempt):
                # Max attempts reached - fail the order
                await order_repo.set_status(order.id, OrderStatus.failed, f"Sonic failed after {order.sonic_attempt} attempts: {error_msg}")
                if order.platform == Platform.telegram and order.user and order.user.telegram_id:
                    await _notify_telegram_order_status(
                        telegram_bot,
                        order.user.telegram_id,
                        f"❌ Не удалось сгенерировать видео для заказа #{order.id} после нескольких попыток.",
                    )
                return web.Response(text="ok")

            # Retry: get audio from order and resubmit
            # Note: We'd need to store audio_base64 or re-fetch from Chatterbox
            # For now, mark for retry and let the monitor handle it
            await order_repo.increment_sonic_attempt(order.id, error_msg)

            # TODO: Implement retry with stored audio_base64
            logger.warning("Sonic retry not fully implemented - needs audio storage")

            return web.Response(text="ok")

        # Success case - send video to user
        video_file_id = output.get("telegram_file_id", "")
        video_url = output.get("video_url", "")

        logger.info("Sonic video generated: order_id=%s job_id=%s file_id=%s", order.id, job_id, video_file_id[:50] if video_file_id else "none")

        # Save video file ID
        if video_file_id:
            await order_repo.set_video_file_id(order.id, video_file_id)

        # Send video to user
        if order.platform == Platform.telegram and order.user and order.user.telegram_id and telegram_bot:
            try:
                if video_file_id:
                    await telegram_bot.send_video(
                        chat_id=order.user.telegram_id,
                        video=video_file_id,
                        caption=f"🎬 Видео готово! Заказ #{order.id}",
                    )
                elif video_url:
                    await telegram_bot.send_message(
                        chat_id=order.user.telegram_id,
                        text=f"🎬 Видео готово! Скачайте по ссылке: {video_url}\nЗаказ #{order.id}",
                    )
                else:
                    await _notify_telegram_order_status(
                        telegram_bot,
                        order.user.telegram_id,
                        f"✅ Видео готово для заказа #{order.id}!",
                    )
            except Exception as exc:
                logger.exception("Failed to send video to user: %s", exc)

    return web.Response(text="ok")


# -------------------------------------------------------------------------
# Application factory with all routes
# -------------------------------------------------------------------------

def create_app(bot: Bot, dispatcher: Dispatcher) -> web.Application:
    app = web.Application()
    app["telegram_bot"] = bot
    app["telegram_dispatcher"] = dispatcher
    app.router.add_get("/health", health)
    app.router.add_post("/webhook/yookassa", yookassa_webhook)
    app.router.add_post("/webhook/chatterbox", chatterbox_webhook)
    app.router.add_post("/webhook/sonic", sonic_webhook)
    app.router.add_post(settings.webhook_path, telegram_webhook)

    # Serve voice samples as static files (e.g. /media/voices/trump.wav → media/voices/trump.wav)
    # This makes the bot's voice samples accessible to RunPod Chatterbox endpoint
    # via reference_audio_url pointing to http://bot-server:8080/media/voices/<voice_sample_path>
    voice_samples_dir = str(Path(__file__).resolve().parents[1] / "media" / "voices")
    app.router.add_static("/media/voices/", voice_samples_dir, show_index=True, follow_symlinks=True)
    logger.info("Static voice samples mounted at /media/voices/ → %s", voice_samples_dir)

    return app
