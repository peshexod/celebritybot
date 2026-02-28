from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db.models import Character, Order


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎬 Создать поздравление", callback_data="create_greeting"))
    builder.row(InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders"))
    builder.row(InlineKeyboardButton(text="❓ Помощь", callback_data="help"))
    return builder.as_markup()


def text_choice_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✍️ Написать свой текст", callback_data="own_text"))
    builder.row(InlineKeyboardButton(text="🤖 Сгенерировать с AI", callback_data="ai_text"))
    return builder.as_markup()


def occasion_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = ["День рождения", "Свадьба", "Новый год", "8 марта", "Юбилей", "Другое"]
    for option in options:
        builder.row(InlineKeyboardButton(text=option, callback_data=f"occasion:{option}"))
    return builder.as_markup()


def text_approval_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Да, нравится", callback_data="text_ok"))
    builder.row(InlineKeyboardButton(text="❌ Нет, сгенерировать заново", callback_data="text_retry"))
    builder.row(InlineKeyboardButton(text="✍️ Отредактировать вручную", callback_data="text_edit"))
    return builder.as_markup()


def characters_keyboard(characters: list[Character], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for character in characters:
        builder.row(InlineKeyboardButton(text=f"Выбрать: {character.name}", callback_data=f"char:{character.id}"))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"char_page:{max(0, page - 1)}"),
        InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"char_page:{page + 1}"),
    )
    return builder.as_markup()


def creative_keyboard(creative_id: int, page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Выбрать этот образ", callback_data=f"creative:{creative_id}"))
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data=f"creative_page:{max(0, page - 1)}"),
        InlineKeyboardButton(text="➡️", callback_data=f"creative_page:{page + 1}"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Другой персонаж", callback_data="change_character"))
    return builder.as_markup()


def order_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Оплатить", callback_data="pay_order"))
    builder.row(InlineKeyboardButton(text="🔙 Изменить текст", callback_data="change_text"))
    builder.row(InlineKeyboardButton(text="🔙 Изменить образ", callback_data="change_creative"))
    builder.row(InlineKeyboardButton(text="🔙 Изменить персонажа", callback_data="change_character"))
    return builder.as_markup()


def payment_url_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Оплатить в ЮКасса", url=url)]])


def orders_keyboard(orders: list[Order], page: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.row(InlineKeyboardButton(text=f"Заказ #{order.id}", callback_data=f"order:{order.id}"))
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data=f"orders_page:{max(0, page - 1)}"),
        InlineKeyboardButton(text="➡️", callback_data=f"orders_page:{page + 1}"),
    )
    return builder.as_markup()
