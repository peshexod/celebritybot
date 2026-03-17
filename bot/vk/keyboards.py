from vkbottle import Keyboard, OpenLink, Text

from bot.config import get_settings
from bot.db.models import Character, Order
from bot.texts import OCCASION_OPTIONS, payment_button_text, payment_link_button_text


settings = get_settings()


def main_menu_keyboard_vk() -> str:
    return (
        Keyboard(one_time=False)
        .add(Text("🎬 Создать поздравление", payload={"cmd": "create_greeting"}))
        .row()
        .add(Text("▶️ Продолжить заказ", payload={"cmd": "resume_order"}))
        .row()
        .add(Text("📋 Мои заказы", payload={"cmd": "my_orders"}))
        .row()
        .add(Text("❓ Помощь", payload={"cmd": "help"}))
        .get_json()
    )


def text_choice_keyboard_vk() -> str:
    return (
        Keyboard(inline=True)
        .add(Text("✍️ Написать свой текст", payload={"cmd": "own_text"}))
        .row()
        .add(Text("🤖 Сгенерировать с AI", payload={"cmd": "ai_text"}))
        .get_json()
    )


def occasion_keyboard_vk() -> str:
    keyboard = Keyboard(inline=True)
    for option in OCCASION_OPTIONS:
        keyboard.add(Text(option, payload={"cmd": "occasion", "value": option})).row()
    return keyboard.get_json()


def text_approval_keyboard_vk() -> str:
    return (
        Keyboard(inline=True)
        .add(Text("✅ Да, нравится", payload={"cmd": "text_ok"}))
        .row()
        .add(Text("❌ Сгенерировать заново", payload={"cmd": "text_retry"}))
        .row()
        .add(Text("✍️ Отредактировать", payload={"cmd": "text_edit"}))
        .get_json()
    )


def characters_keyboard_vk(character: Character, page: int) -> str:
    return (
        Keyboard(inline=True)
        .add(Text(f"Выбрать: {character.name}", payload={"cmd": "char", "character_id": character.id}))
        .row()
        .add(Text("⬅️ Назад", payload={"cmd": "char_page", "page": page - 1}))
        .add(Text("➡️ Вперёд", payload={"cmd": "char_page", "page": page + 1}))
        .get_json()
    )


def creative_keyboard_vk(creative_id: int, page: int) -> str:
    return (
        Keyboard(inline=True)
        .add(Text("Выбрать этот образ", payload={"cmd": "creative", "creative_id": creative_id}))
        .row()
        .add(Text("⬅️ Предыдущий", payload={"cmd": "creative_page", "page": page - 1}))
        .add(Text("➡️ Следующий", payload={"cmd": "creative_page", "page": page + 1}))
        .row()
        .add(Text("🔙 Другой персонаж", payload={"cmd": "change_character"}))
        .get_json()
    )


def order_confirm_keyboard_vk() -> str:
    return (
        Keyboard(inline=True)
        .add(Text(payment_button_text(settings.order_price), payload={"cmd": "pay_order"}))
        .row()
        .add(Text("🔙 Изменить текст", payload={"cmd": "change_text"}))
        .row()
        .add(Text("🔙 Изменить образ", payload={"cmd": "change_creative"}))
        .row()
        .add(Text("🔙 Изменить персонажа", payload={"cmd": "change_character"}))
        .get_json()
    )


def payment_url_keyboard_vk(url: str) -> str:
    return Keyboard(inline=True).add(OpenLink(url, payment_link_button_text(settings.order_price))).get_json()


def orders_keyboard_vk(orders: list[Order], page: int) -> str:
    keyboard = Keyboard(inline=True)
    for order in orders:
        keyboard.add(Text(f"Заказ #{order.id}", payload={"cmd": "order", "order_id": order.id})).row()
    keyboard.add(Text("⬅️", payload={"cmd": "orders_page", "page": max(0, page - 1)}))
    keyboard.add(Text("➡️", payload={"cmd": "orders_page", "page": page + 1}))
    return keyboard.get_json()
