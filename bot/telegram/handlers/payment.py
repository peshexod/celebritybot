from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.shared import initiate_payment_common
from bot.services.payment_service import PaymentConfigurationError
from bot.texts import PAYMENT_CONFIGURATION_ERROR_TEXT, PAYMENT_WAITING_TEXT
from bot.telegram.keyboards import payment_url_keyboard
from bot.telegram.states import PaymentFSM


router = Router()


@router.callback_query(F.data == "pay_order")
async def create_payment(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        payment = await initiate_payment_common(int(data["order_id"]), session)
    except PaymentConfigurationError:
        await callback.message.answer(PAYMENT_CONFIGURATION_ERROR_TEXT)
        await callback.answer()
        return

    await state.set_state(PaymentFSM.waiting_payment)
    await callback.message.answer(PAYMENT_WAITING_TEXT, reply_markup=payment_url_keyboard(payment.payment_url))
    await callback.answer()
