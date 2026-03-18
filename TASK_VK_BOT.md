# ТЗ: Реализация VK-версии бота с переиспользованием бизнес-логики

## Цель

Добавить полноценную поддержку VK (ВКонтакте) в бота для генерации видео-поздравлений. VK-бот должен иметь тот же user flow, что и Telegram-версия.

## Текущее состояние

- ✅ Telegram бот: полный user flow (start, выбор celebrity, персонаж, оплата, генерация)
- ✅ Общие сервисы: `order_service`, `payment_service`, `chatterbox_service`, `video_service`
- ✅ Общие модели БД и repositories
- ❌ VK бот: заглушка — только ответ на /start

## Архитектура

### Вариант: Частичное переиспользование (вариант 2)

Структура:
```
bot/
├── handlers/
│   ├── shared/              # Общая бизнес-логика (платформо-agnostic)
│   │   ├── start_logic.py
│   │   ├── greeting_logic.py
│   │   ├── character_logic.py
│   │   ├── payment_logic.py
│   │   └── orders_logic.py
│   ├── telegram/           # Telegram-специфичный код (aiogram)
│   │   ├── start.py
│   │   ├── greeting.py
│   │   ├── character.py
│   │   ├── payment.py
│   │   └── orders.py
│   └── vk/                 # VK-специфичный код (vkbottle)
│       ├── start.py
│       ├── greeting.py
│       ├── character.py
│       ├── payment.py
│       └── orders.py
```

### Принципы

1. **Общая логика (`shared/`):** Не зависит от aiogram/vkbottle. Работает с DB, services, state.

2. **Платформо-зависимые wrappers:** 
   - Telegram: `message.answer()`, `callback.answer()`, `InlineKeyboardMarkup`
   - VK: `message.answer()`, клавиатуры VK-формата

3. **Минимальное дублирование:** Только "обёртки" вокруг общей логики.

## Файлы для реализации

### 1. Создать общую логику

#### `bot/handlers/shared/__init__.py`
```python
# Exports for shared logic modules
```

#### `bot/handlers/shared/start_logic.py`
- `handle_start_common(user_id, username, session)` — создать/получить юзера
- `handle_resume_order_common(order_id, session)` — восстановить заказ

#### `bot/handlers/shared/greeting_logic.py`
- `handle_greeting_common(user_id, session)` — показать главное меню
- `handle_choose_ai_text_common(user_id, session)` — выбор AI текста
- `handle_choose_own_text_common(user_id, session)` — выбор своего текста
- `handle_ai_generation_common(user_id, text, session)` — генерация AI текста

#### `bot/handlers/shared/character_logic.py`
- `start_browsing_common(user_id, page, session)` — начать просмотр персонажей
- `get_characters_page_common(page, session)` — получить страницу персонажей
- `select_character_common(character_id, session)` — выбрать персонажа
- `select_creative_common(creative_id, session)` — выбрать образ

#### `bot/handlers/shared/payment_logic.py`
- `create_order_common(user_id, text, character_id, creative_id, platform, session)` — создать заказ
- `initiate_payment_common(order_id, session)` — инициировать оплату
- `handle_payment_success_common(order_id, session)` — обработка успешной оплаты

#### `bot/handlers/shared/orders_logic.py`
- `get_user_orders_common(user_id, session)` — получить список заказов
- `get_order_details_common(order_id, session)` — детали заказа

### 2. Адаптировать Telegram handlers

Обновить существующие файлы в `bot/handlers/telegram/`:
- Импортировать соответствующую логику из `shared/`
- Оставить только платформо-зависимый код (aiogram)

### 3. Создать VK handlers

Создать новые файлы в `bot/handlers/vk/`:

#### `bot/handlers/vk/__init__.py`
```python
from vkbottle import Router

router = Router()
```

#### `bot/handlers/vk/start.py`
- Обработка /start
- resume_order callback
- help команда

#### `bot/handlers/vk/greeting.py`
- Главное меню
- Выбор AI/свой текст
- AI генерация текста

#### `bot/handlers/vk/character.py`
- Просмотр персонажей (пагинация)
- Выбор персонажа и образа
- Подтверждение заказа

#### `bot/handlers/vk/payment.py`
- Создание заказа
- Оплата через YooKassa
- Уведомление об оплате

#### `bot/handlers/vk/orders.py`
- Просмотр истории заказов

### 4. Обновить VK bot.py

```python
from vkbottle import API, Bot
from bot.handlers.vk import start, greeting, character, payment, orders

def build_vk_bot() -> Bot:
    settings = get_settings()
    api = API(settings.vk_bot_token)
    bot = Bot(api=api)
    
    # Register handlers
    bot.on.message(start.start_handler)
    bot.on.callback(greeting.greeting_callback)
    # ... etc
    
    return bot
```

### 5. Обновить main.py

Добавить запуск VK polling и webhook:

```python
async def run_polling() -> None:
    tg_bot = build_telegram_bot()
    await setup_telegram_commands(tg_bot)
    tg_dp = build_telegram_dispatcher()
    
    vk_bot = build_vk_bot()
    
    # Запустить оба
    await asyncio.gather(
        tg_dp.start_polling(tg_bot),
        vk_bot.run_polling()
    )


async def run_webhook() -> None:
    # Telegram webhook
    tg_bot = build_telegram_bot()
    await setup_telegram_commands(tg_bot)
    tg_dp = build_telegram_dispatcher()
    tg_webhook_url = f"{settings.webhook_host.rstrip('/')}{settings.telegram_webhook_path}"
    await tg_bot.set_webhook(url=tg_webhook_url, ...)

    # VK webhook
    vk_webhook_url = f"{settings.webhook_host.rstrip('/')}{settings.vk_webhook_path}"
    await vk_bot.set_webhook(url=vk_webhook_url)
    
    # Запустить веб-сервер для обоих ботов
    app = create_app(tg_bot, tg_dp, vk_bot)
    ...
```

### VK Webhook

Добавить в конфиг:
- `VK_WEBHOOK_PATH` — путь для VK webhook (например, `/webhook/vk`)

Добавить в `main.py`:
- Обработка VK events через webhook
- Endpoint для VK webhook в `bot/web/webhooks.py`

## Клавиатуры

Создать VK-версии клавиатур в `bot/vk/keyboards.py`:
- `main_menu_keyboard_vk()` — главное меню
- `characters_keyboard_vk()` — навигация по персонажам
- `order_confirm_keyboard_vk()` — подтверждение заказа

## State management

Для VK использовать vkbottle state:
```python
from vkbottle import FSM, BaseStateGroup

class UserState(BaseStateGroup):
    GREETING = "greeting"
    CHOOSING_TEXT = "choosing_text"
    BROWSING_CHARACTERS = "browsing"
    # ...
```

## Пример迁移 (示例)

### Было (Telegram only):

```python
# bot/handlers/telegram/start.py
@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    user_repo = UserRepository(session)
    await user_repo.get_or_create_telegram_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "Привет! Я помогу создать поздравительный видео-кружок. Выберите действие:",
        reply_markup=main_menu_keyboard(),
    )
```

### Станет:

```python
# bot/handlers/shared/start_logic.py
async def handle_start_common(user_id: int, username: str | None, platform: str, session: AsyncSession):
    user_repo = UserRepository(session)
    await user_repo.get_or_create_user(user_id, username, platform)
    return True

# bot/handlers/telegram/start.py (обновлённый)
@router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession) -> None:
    from bot.handlers.shared.start_logic import handle_start_common
    
    await handle_start_common(
        message.from_user.id,
        message.from_user.username,
        "telegram",
        session
    )
    await message.answer(
        "Привет! Я помогу создать поздравительный видео-кружок. Выберите действие:",
        reply_markup=main_menu_keyboard(),
    )

# bot/handlers/vk/start.py (новый)
@router.message_handler(text="/start")
async def start_handler(message: Message, session: AsyncSession) -> None:
    from bot.handlers.shared.start_logic import handle_start_common
    
    await handle_start_common(
        message.from_id,
        message.from_user.username if hasattr(message, 'from_user') else None,
        "vk",
        session
    )
    await message.answer(
        "Привет! Я помогу создать поздравительный видео-кружок. Выберите действие:",
        keyboard=main_menu_keyboard_vk(),
    )
```

## Критерии приёмки

1. ✅ VK бот отвечает на /start и показывает главное меню
2. ✅ Можно выбрать AI текст или свой текст
3. ✅ Можно просматривать персонажей с пагинацией
4. ✅ Можно выбрать персонажа и образ
5. ✅ Можно создать заказ и оплатить
6. ✅ Приходит уведомление о результате генерации
7. ✅ Работает просмотр истории заказов
8. ✅ Общая бизнес-логика не дублируется
9. ✅ При изменении логики в shared/ — изменения применяются к обеим платформам

## Приоритеты

1. **P0 (MVP):** start, greeting, character browsing, создание заказа
2. **P1:** оплата, генерация, уведомления
3. **P2:** история заказов, помощь

## Тексты и константы

Вынести все hardcoded строки в единое место:

```
bot/
├── texts.py  # или bot/constants/texts.py
```

Содержит:
- `GREETING_TEXT` — "Привет! Я помогу создать поздравительный видео-кружок..."
- `MAIN_MENU_TEXT` — текст главного меню
- `HELP_TEXT` — справка
- `PAYMENT_TEXT` — тексты оплаты
- `ERROR_TEXT` — сообщения об ошибках
- И т.д.

Пример:
```python
# bot/texts.py
GREETING_TEXT = "Привет! Я помогу создать поздравительный видео-кружок. Выберите действие:"
HELP_TEXT = "1) Создайте текст вручную или через AI\n2) Выберите персонажа и образ\n3) Оплатите заказ\n4) Дождитесь генерации видео"
# ...
```

## Заметки

- VK API имеет лимиты и особенности (например, callback кнопки работают иначе)
- Использовать Long Polling для VK (vkbottle)
- Проверить работу с VK keyboard (CallbackButtons vs InlineKeyboard)
- Для webhook режима — добавить VK webhook endpoint
