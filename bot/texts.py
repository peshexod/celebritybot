from decimal import Decimal


def _format_price(value: int | float | Decimal) -> str:
    amount = Decimal(value)
    if amount == amount.to_integral_value():
        return f"{int(amount)} руб"
    return f"{amount:.2f} руб"


GREETING_TEXT = "Привет! Я помогу создать поздравительный видео-кружок. Выберите действие:"
HELP_TEXT = (
    "1) Создайте текст вручную или через AI\n"
    "2) Выберите персонажа и образ\n"
    "3) Оплатите заказ\n"
    "4) Дождитесь генерации видео"
)
TEXT_CHOICE_TEXT = "Выберите способ ввода текста:"
OWN_TEXT_PROMPT = "Отправьте текст поздравления (до {max_length} символов)."
EDITED_TEXT_PROMPT = "Отправьте отредактированный текст."
CHANGE_TEXT_PROMPT = "Отправьте новый текст поздравления (до {max_length} символов)."
TEXT_TOO_LONG_TEXT = "Текст слишком длинный. Максимум {max_length} символов."
RECIPIENT_NAME_PROMPT = "Как зовут получателя?"
OCCASION_PROMPT = "Какой повод?"
DETAILS_PROMPT = "Хотите добавить детали или пожелания? Напишите текст или отправьте 'Пропустить'."
GENERATING_TEXT = "Генерирую текст..."
TEXT_APPROVAL_TEXT = "Текст для согласования:\n\n{text}"
AI_TEXT_APPROVAL_TEXT = "Вариант поздравления:\n\n{text}"
REGENERATED_TEXT_APPROVAL_TEXT = "Новый вариант:\n\n{text}"
MAX_REGEN_ATTEMPTS_TEXT = "Достигнут лимит попыток. Введите текст вручную."
EMPTY_CHARACTERS_TEXT = "Список персонажей пока пуст."
NO_ACTIVE_ORDER_TEXT = "Активных заказов не найдено. Начните новый через «Создать поздравление»."
ORDER_CONTEXT_LOST_TEXT = "Контекст предыдущего шага утерян. Нажмите «Создать поздравление» или «Продолжить заказ»."
CONTINUE_CHARACTER_CHOICE_TEXT = "Продолжаем выбор персонажа"
NO_MORE_CHARACTERS_TEXT = "Больше персонажей нет."
NO_MORE_CREATIVES_TEXT = "Больше образов нет."
ORDER_ALREADY_PROCESSED_TEXT = "Последний заказ #{order_id} уже в статусе {status}. Откройте «Мои заказы» для деталей."
RESUMED_ORDER_TEXT = (
    "Восстановлен заказ:\n\n"
    "Текст: {text}\n"
    "Персонаж: {character}\n"
    "Образ: {creative}"
)
CHARACTER_RESTORE_FAILED_TEXT = "Не удалось восстановить выбранного персонажа. Выберите его заново."
NO_CREATIVES_TEXT = "Для персонажа нет образов."
SELECT_IMAGE_TEXT = "Выберите этот образ"
ORDER_CONFIRMATION_TEXT = (
    "Проверьте заказ:\n\n"
    "Текст: {text}\n"
    "Персонаж: {character}\n"
    "Образ: {creative}"
)
PAYMENT_WAITING_TEXT = "Для продолжения оплатите заказ. После оплаты мы подтвердим платёж автоматически в фоне."
PAYMENT_CONFIGURATION_ERROR_TEXT = "Оплата сейчас недоступна. Попробуйте позже или обратитесь в поддержку."
ORDERS_EMPTY_TEXT = "У вас пока нет заказов."
ORDERS_PAGE_EMPTY_TEXT = "Нет заказов на этой странице."
ORDERS_HEADER_TEXT = "Ваши заказы:\n{rows}"
ORDER_INVALID_TEXT = "Некорректный заказ."
ORDER_NOT_FOUND_TEXT = "Заказ не найден."
ORDER_DETAILS_TEXT = (
    "Заказ #{order_id}\n"
    "Статус: {status}\n"
    "Попытка: {attempt}/{max_attempts}\n"
    "Текст: {text}"
)
ORDER_ERROR_TEXT = "Ошибка: {error}"
PAYMENT_SUCCESS_TEXT = "✅ Оплата получена по заказу #{order_id}. Запускаю генерацию."
PAYMENT_INITIATED_TEXT = "Оплата создана для заказа #{order_id}."
AI_READY_TEXT = "🎤 Аудио готово! Запускаю генерацию видео..."
VIDEO_STARTED_TEXT = "🎬 Генерация видео запущена для заказа #{order_id}."
RETRYING_TEXT = "⚠️ По заказу #{order_id} возникла ошибка генерации. Мы пробуем повторно."
CHATTERBOX_FAILED_TEXT = "❌ Не удалось сгенерировать аудио для заказа #{order_id} после нескольких попыток."
VIDEO_FAILED_TEXT = "❌ Не удалось сгенерировать видео для заказа #{order_id} после нескольких попыток."
VIDEO_READY_TEXT = "🎬 Видео готово! Заказ #{order_id}"
VIDEO_READY_WITH_LINK_TEXT = "🎬 Видео готово! Скачайте по ссылке: {video_url}\nЗаказ #{order_id}"
VIDEO_READY_STATUS_TEXT = "✅ Видео готово для заказа #{order_id}!"

OCCASION_OPTIONS = ["День рождения", "Свадьба", "Новый год", "8 марта", "Юбилей", "Другое"]

STATUS_LABELS = {
    "pending_payment": "⏳ Ожидает оплаты",
    "paid": "💳 Оплачен",
    "generating_audio": "🔄 Генерация аудио",
    "generating_video": "🔄 Генерируется",
    "retrying": "🔄 Повторная попытка",
    "completed": "✅ Готово",
    "refunded": "💸 Возврат средств",
    "failed": "❌ Ошибка",
}


def main_menu_text() -> str:
    return GREETING_TEXT


def own_text_prompt(max_length: int) -> str:
    return OWN_TEXT_PROMPT.format(max_length=max_length)


def change_text_prompt(max_length: int) -> str:
    return CHANGE_TEXT_PROMPT.format(max_length=max_length)


def text_too_long_text(max_length: int) -> str:
    return TEXT_TOO_LONG_TEXT.format(max_length=max_length)


def text_approval_text(text: str, ai_generated: bool = False, regenerated: bool = False) -> str:
    if regenerated:
        return REGENERATED_TEXT_APPROVAL_TEXT.format(text=text)
    if ai_generated:
        return AI_TEXT_APPROVAL_TEXT.format(text=text)
    return TEXT_APPROVAL_TEXT.format(text=text)


def character_caption(name: str, description: str, page: int, total: int) -> str:
    return f"{name} ({page + 1}/{total})\n{description}"


def creative_caption(label: str | None, page: int, total: int) -> str:
    return f"{label or SELECT_IMAGE_TEXT} ({page + 1}/{total})"


def resumed_order_text(text: str, character: str, creative: str) -> str:
    return RESUMED_ORDER_TEXT.format(text=text, character=character, creative=creative)


def order_confirmation_text(text: str, character: str, creative: str) -> str:
    return ORDER_CONFIRMATION_TEXT.format(text=text, character=character, creative=creative)


def payment_button_text(price: int | float | Decimal) -> str:
    return f"💳 Оплатить {_format_price(price)}"


def payment_link_button_text(price: int | float | Decimal) -> str:
    return f"Оплатить {_format_price(price)} в ЮKassa"


def payment_description(order_id: int) -> str:
    return f"Оплата заказа #{order_id}"


def order_processed_text(order_id: int, status: str) -> str:
    return ORDER_ALREADY_PROCESSED_TEXT.format(order_id=order_id, status=status)


def order_ready_for_payment_text(order_id: int) -> str:
    return PAYMENT_INITIATED_TEXT.format(order_id=order_id)


def payment_success_text(order_id: int) -> str:
    return PAYMENT_SUCCESS_TEXT.format(order_id=order_id)


def video_started_text(order_id: int) -> str:
    return VIDEO_STARTED_TEXT.format(order_id=order_id)


def retrying_text(order_id: int) -> str:
    return RETRYING_TEXT.format(order_id=order_id)


def chatterbox_failed_text(order_id: int) -> str:
    return CHATTERBOX_FAILED_TEXT.format(order_id=order_id)


def video_failed_text(order_id: int) -> str:
    return VIDEO_FAILED_TEXT.format(order_id=order_id)


def video_ready_text(order_id: int) -> str:
    return VIDEO_READY_TEXT.format(order_id=order_id)


def video_ready_with_link_text(order_id: int, video_url: str) -> str:
    return VIDEO_READY_WITH_LINK_TEXT.format(order_id=order_id, video_url=video_url)


def video_ready_status_text(order_id: int) -> str:
    return VIDEO_READY_STATUS_TEXT.format(order_id=order_id)


def order_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def order_row_text(order_id: int, status: str, attempt: int) -> str:
    return f"#{order_id} | {order_status_label(status)} | попытка {attempt}"


def orders_text(rows: list[str]) -> str:
    return ORDERS_HEADER_TEXT.format(rows="\n".join(rows))


def order_details_text(order_id: int, status: str, attempt: int, max_attempts: int, text: str, error: str | None = None) -> str:
    body = ORDER_DETAILS_TEXT.format(
        order_id=order_id,
        status=order_status_label(status),
        attempt=attempt,
        max_attempts=max_attempts,
        text=text,
    )
    if error:
        body = f"{body}\n{ORDER_ERROR_TEXT.format(error=error)}"
    return body
