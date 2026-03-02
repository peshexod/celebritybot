import json
import logging

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Update

from bot.config import get_settings
from bot.db.database import SessionLocal
from bot.db.models import OrderStatus, PaymentStatus, Platform
from bot.db.repositories import OrderRepository, PaymentRepository
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


def create_app(bot: Bot, dispatcher: Dispatcher) -> web.Application:
    app = web.Application()
    app["telegram_bot"] = bot
    app["telegram_dispatcher"] = dispatcher
    app.router.add_get("/health", health)
    app.router.add_post("/webhook/yookassa", yookassa_webhook)
    app.router.add_post(settings.webhook_path, telegram_webhook)
    return app
