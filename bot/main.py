import asyncio
import logging

from aiohttp import web

from bot.config import get_settings
from bot.db.database import SessionLocal
from bot.db.models import OrderStatus, PaymentStatus, Platform
from bot.db.repositories import OrderRepository, PaymentRepository
from bot.services.order_service import OrderService
from bot.services.payment_service import PaymentService
from bot.services.video_service import VideoService
from bot.services.voice_service import VoiceService
from bot.telegram.bot import build_bot, build_dispatcher, setup_bot_commands
from bot.web.webhooks import create_app


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
settings = get_settings()


def _resolve_platform_target(order) -> tuple[str | None, str]:
    if order.platform == Platform.telegram:
        return str(order.user.telegram_id or ""), settings.telegram_bot_token
    if order.platform == Platform.vk:
        return str(order.user.vk_id or ""), settings.vk_bot_token
    return None, settings.telegram_bot_token


async def _start_generation_for_paid_order(session, order_id: int) -> None:
    order_repo = OrderRepository(session)
    order = await order_repo.get_order_with_user(order_id)
    if not order or not order.user:
        return

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


async def _process_pending_payment(session, payment, payment_service: PaymentService) -> None:
    payment_repo = PaymentRepository(session)
    order_repo = OrderRepository(session)

    status = await payment_service.check_payment(payment.yookassa_payment_id)
    if status != "succeeded":
        return

    await payment_repo.set_status(payment.yookassa_payment_id, PaymentStatus.succeeded)
    await order_repo.mark_paid(payment.order_id, payment.yookassa_payment_id)
    await _start_generation_for_paid_order(session, payment.order_id)


async def monitor_stuck_orders() -> None:
    while True:
        try:
            async with SessionLocal() as session:
                repo = OrderRepository(session)
                stuck = await repo.list_stuck_orders(older_than_minutes=15)
                for order in stuck:
                    if order.attempt_number >= order.max_attempts:
                        await repo.set_status(order.id, OrderStatus.failed, "Timeout waiting runpod job")
                    else:
                        await repo.increment_attempt(order.id, "Timeout waiting runpod job")
        except Exception as exc:
            logger.exception("Monitor error: %s", exc)
        await asyncio.sleep(120)


async def monitor_pending_payments() -> None:
    payment_service = PaymentService()
    while True:
        try:
            async with SessionLocal() as session:
                payment_repo = PaymentRepository(session)
                pending_payments = await payment_repo.list_pending(limit=50)
                for payment in pending_payments:
                    await _process_pending_payment(session, payment, payment_service)
        except Exception as exc:
            logger.exception("Payment monitor error: %s", exc)
        await asyncio.sleep(10)


async def run_polling() -> None:
    bot = build_bot()
    await setup_bot_commands(bot)
    dp = build_dispatcher()
    monitor_task = asyncio.create_task(monitor_stuck_orders())
    payment_monitor_task = asyncio.create_task(monitor_pending_payments())
    try:
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        payment_monitor_task.cancel()
        await bot.session.close()


async def run_webhook() -> None:
    bot = build_bot()
    await setup_bot_commands(bot)
    dp = build_dispatcher()
    webhook_url = f"{settings.webhook_host.rstrip('/')}{settings.webhook_path}"
    await bot.set_webhook(
        url=webhook_url,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    webhook_info = await bot.get_webhook_info()
    logger.info("Telegram webhook set to: %s", webhook_info.url)

    monitor_task = asyncio.create_task(monitor_stuck_orders())
    app = create_app(bot, dp)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("Webhook server started on :8080")
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        monitor_task.cancel()
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.session.close()
        await runner.cleanup()


async def main() -> None:
    if settings.bot_mode == "webhook":
        await run_webhook()
    else:
        await run_polling()


if __name__ == "__main__":
    asyncio.run(main())
