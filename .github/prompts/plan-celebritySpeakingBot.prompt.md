## Plan: Celebrity Greeting Video Bot (Telegram + VK)

**TL;DR** — Бот для Telegram и ВК, позволяющий пользователю сгенерировать поздравительный видеокружок с голосом и лицом знаменитости. Пользователь пишет текст сам или генерирует через AI (GPT-4o-mini via OpenRouter, до 5 попыток), выбирает персонажа из динамического списка в БД, оплачивает через ЮКассу, после чего система генерирует аудио (ElevenLabs TTS) и отправляет на RunPod для создания видео. RunPod сам отправляет готовое видео пользователю. Архитектура: monorepo, Docker Compose, PostgreSQL, polling (dev) / webhook (prod).

---

### Юзерфлоу бота (детально)

**1. Старт**
- Пользователь отправляет `/start`
- Бот приветствует и показывает главное меню (inline keyboard):
  - `🎬 Создать поздравление`
  - `📋 Мои заказы`
  - `❓ Помощь`

**2. Выбор способа ввода текста**
- Пользователь нажимает «Создать поздравление»
- Бот предлагает два варианта:
  - `✍️ Написать свой текст`
  - `🤖 Сгенерировать с AI`

**3a. Свой текст**
- Бот: «Отправьте текст поздравления (до 500 символов / ~100 слов / ~30 сек озвучки)»
- Пользователь вводит текст → валидация длины → переход к шагу 4

**3b. Генерация текста AI**
- Бот задаёт вопросы последовательно (FSM states):
  1. «Как зовут получателя?» → свободный текст
  2. «Какой повод?» → inline-кнопки: `День рождения`, `Свадьба`, `Новый год`, `8 марта`, `Юбилей`, `Другое` (+ свободный ввод)
  3. «Хотите добавить детали или пожелания?» → свободный текст + кнопка `Пропустить`
- Бот: «Генерирую текст...» → вызов OpenRouter API (GPT-4o-mini) → показ текста
- Кнопки: `✅ Да, нравится` / `❌ Нет, сгенерировать заново` / `✍️ Отредактировать вручную`
- При «Нет» — повтор генерации, **лимит 5 попыток**, после чего предложить ввести вручную
- При «Отредактировать» — пользователь отправляет исправленный текст

**4. Выбор персонажа (2-шаговый)**

**4a. Шаг 1 — выбор персонажа**
- Бот показывает список персонажей (из БД) — пагинация inline-кнопками
- Каждый персонаж: превью-фото + имя + краткое описание
- Навигация: `⬅️ Назад` / `➡️ Вперёд` / кнопка выбора под каждым персонажем
- Пользователь нажимает на персонажа → переход к шагу 4b

**4b. Шаг 2 — выбор креатива/изображения**
- Бот показывает все доступные креативы (изображения) выбранного персонажа — галерея с пагинацией
- Каждый креатив: фото в чат + inline-кнопка `Выбрать этот образ`
- Навигация: `⬅️` / `➡️` между креативами + `🔙 Другой персонаж` (возврат к шагу 4a)
- Пользователь выбирает конкретный креатив → подтверждение: показ итога (текст + персонаж + выбранный образ + цена)
- Кнопки: `💳 Оплатить` / `🔙 Изменить текст` / `🔙 Изменить образ` / `🔙 Изменить персонажа`

**5. Оплата (ЮКасса)**
- Создаём платёж через `yookassa` Python SDK
- Отправляем пользователю ссылку на оплату (inline-кнопка с URL)
- Webhook от ЮКассы подтверждает платёж → обновляем статус заказа в БД
- Fallback: polling статуса платежа (для dev-режима)

**6. Генерация аудио + видео**
- После подтверждения платежа:
  1. Вызов ElevenLabs TTS API: текст → mp3 (голос персонажа по `voice_id`)
  2. Кодируем аудио (mp3) и изображение выбранного креатива в base64
  3. Отправляем запрос на RunPod с `user_id`, `bot_token`, `image_input`, `audio_input`
  4. Получаем `job_id` → сохраняем в БД
- Бот отправляет: «Ваше видео генерируется ⏳ Обычно это занимает 2-5 минут»
- RunPod по завершении сам отправляет видео в чат пользователю
- Для VK: аналогичный механизм (когда RunPod сделает поддержку VK)

**7. Мои заказы**
- Список заказов пользователя с пагинацией
- Статусы: `⏳ Ожидает оплаты` / `💳 Оплачен` / `🔄 Генерируется` / `🔄 Повторная попытка` / `✅ Готово` / `💸 Возврат средств` / `❌ Ошибка`
- По каждому заказу: персонаж, образ, дата, текст, статус, номер попытки
- Для завершённых: кнопка «Повторить заказ»
- Для возвращённых: информация о возврате средств

---

### Шаги реализации

**Step 1. Структура проекта и конфигурация**
- Создать структуру:
  ```
  bot/
  ├── __init__.py
  ├── main.py              # точка входа, запуск ботов
  ├── config.py             # Settings через pydantic-settings (.env)
  ├── db/
  │   ├── __init__.py
  │   ├── models.py         # SQLAlchemy models
  │   ├── database.py       # engine, session factory
  │   └── repositories.py   # CRUD операции
  ├── telegram/
  │   ├── __init__.py
  │   ├── bot.py            # инициализация aiogram Bot + Dispatcher
  │   ├── handlers/
  │   │   ├── start.py      # /start, главное меню
  │   │   ├── greeting.py   # создание поздравления (FSM)
  │   │   ├── character.py  # выбор персонажа
  │   │   ├── payment.py    # оплата ЮКасса
  │   │   └── orders.py     # история заказов
  │   ├── keyboards.py      # все inline/reply keyboards
  │   ├── states.py         # FSM states
  │   └── middlewares.py    # DB session middleware
  ├── vk/
  │   ├── __init__.py
  │   ├── bot.py            # инициализация VK бота
  │   └── handlers/         # зеркальные обработчики для VK
  ├── services/
  │   ├── __init__.py
  │   ├── voice_service.py  # ElevenLabs TTS (переписать текущий на TTS)
  │   ├── video_service.py  # RunPod API
  │   ├── ai_service.py     # OpenRouter (генерация текста)
  │   └── payment_service.py # ЮКасса
  ├── web/
  │   └── webhooks.py       # aiohttp сервер для webhook'ов (TG, ЮКасса)
  └── utils/
      └── helpers.py
  docker-compose.yml
  docker-compose.prod.yml
  Dockerfile
  .env.example
  requirements.txt
  alembic/                   # миграции БД
  alembic.ini
  media/
  └── characters/            # изображения персонажей
  ```

**Step 2. Модели базы данных (SQLAlchemy + asyncpg)**
- Таблица `users`: `id`, `telegram_id`, `vk_id`, `username`, `created_at`
- Таблица `characters`: `id`, `name`, `description`, `preview_image_path`, `elevenlabs_voice_id`, `is_active`, `sort_order`, `created_at`
- Таблица `character_creatives`: `id`, `character_id` (FK → characters), `image_path`, `label` (опциональное название образа), `is_active`, `sort_order`, `created_at`
  - Связь: один персонаж → много креативов (изображений/образов)
- Таблица `orders`: `id`, `user_id` (FK), `character_id` (FK), `creative_id` (FK → character_creatives), `text`, `status` (enum: pending_payment, paid, generating_audio, generating_video, completed, failed, retrying, refunded), `payment_id`, `runpod_job_id`, `attempt_number` (int, default 1), `max_attempts` (int, default 3), `price`, `platform` (telegram/vk), `error_message`, `created_at`, `updated_at`
- Таблица `payments`: `id`, `order_id` (FK), `yookassa_payment_id`, `amount`, `status` (enum: pending, succeeded, refunded, failed), `refund_id` (nullable), `created_at`, `refunded_at` (nullable)
- Настроить Alembic для миграций

**Step 3. config.py — переменные окружения**
- `BOT_MODE` (polling/webhook)
- `TELEGRAM_BOT_TOKEN`
- `VK_BOT_TOKEN`, `VK_GROUP_ID`
- `DATABASE_URL`
- `ELEVENLABS_API_KEY`
- `OPENROUTER_API_KEY`
- `RUNPOD_API_KEY`, `RUNPOD_ENDPOINT`
- `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`
- `WEBHOOK_HOST`, `WEBHOOK_PATH`
- `ORDER_PRICE` (фиксированная цена)
- `MAX_TEXT_LENGTH` (500 символов)
- `MAX_REGEN_ATTEMPTS` (5)

**Step 4. Сервисы**
- **ai_service.py**: Обёртка над OpenRouter API. Промпт для генерации поздравлений на русском с параметрами (имя, повод, детали). Использовать `aiohttp` для async HTTP. Модель: `openai/gpt-4o-mini`.
- **voice_service.py**: **Переписать** текущий STS на TTS. Использовать `elevenlabs` Python SDK, метод `client.text_to_speech.convert()` с `voice_id` персонажа. Async обёртка через `asyncio.to_thread()` если SDK синхронный.
- **video_service.py**: Async клиент для RunPod API. Методы: `submit_job(user_id, bot_token, creative_image_base64, audio_base64) → job_id`, `get_job_status(job_id) → status`. Для VK: передавать VK-специфичные параметры (когда RunPod поддержит). Изображение берётся из выбранного креатива (`character_creatives.image_path`).
- **payment_service.py**: Обёртка ЮКасса SDK. Методы: `create_payment(order_id, amount, description) → payment_url`, `check_payment(payment_id) → status`, `create_refund(payment_id, amount) → refund_id`. Webhook handler для подтверждения оплаты и возврата.

**Step 5. Telegram бот (aiogram 3.x)**
- FSM States в `states.py`:
  - `GreetingFSM`: `waiting_text_choice`, `waiting_own_text`, `waiting_recipient_name`, `waiting_occasion`, `waiting_details`, `waiting_text_approval`
  - `CharacterFSM`: `browsing_characters`, `browsing_creatives`, `confirming_order`
  - `PaymentFSM`: `waiting_payment`
- Handlers:
  - `start.py`: `/start` → приветствие + меню. `/help` → инструкция
  - `greeting.py`: FSM для всего флоу ввода/генерации текста
  - `character.py`: Показ персонажей (фото + inline кнопки), пагинация, выбор
  - `payment.py`: Создание платежа, отправка ссылки, webhook обработка
  - `orders.py`: `/orders` → список заказов, статусы, пагинация
- DB middleware: инъекция async session в каждый handler

**Step 6. VK бот**
- Использовать `vkbottle` (async библиотека для VK ботов)
- Зеркальная реализация handlers из Telegram
- Общие сервисы (ai, voice, video, payment) — те же самые
- Различия: формат клавиатур (VK Keyboard vs Telegram InlineKeyboard), отправка медиа (загрузка на VK серверы)

**Step 7. Web-сервер (aiohttp)**
- Единый aiohttp-сервер для:
  - Telegram webhook (`POST /webhook/telegram`)
  - ЮКасса webhook (`POST /webhook/yookassa`)
  - Health check (`GET /health`)
- В dev-режиме: только ЮКасса webhook + polling для TG/VK
- В prod-режиме: все webhooks

**Step 8. Docker и CI/CD**
- `Dockerfile`: multi-stage build, Python 3.12 slim
- `docker-compose.yml` (dev): бот (polling mode) + PostgreSQL + pgAdmin (опционально)
- `docker-compose.prod.yml`: бот (webhook mode) + PostgreSQL + nginx (для SSL/webhook)
- GitHub Actions: lint (ruff) → test → build → deploy (SSH + docker compose up)

**Step 9. Обработка ошибок и гарантия результата**

Принцип: **клиент всегда получает либо результат, либо возврат денег**. Ни одна оплата не должна остаться без результата.

- **Политика retry (автоматические повторные попытки)**:
  - При ошибке ElevenLabs TTS: автоматический retry до 3 попыток с экспоненциальной задержкой (5с, 15с, 45с)
  - При ошибке RunPod: автоматический retry до 3 попыток (повторная отправка job)
  - Таймаут RunPod: если видео не готово через 60 минут → автоматический retry (новый job)
  - Каждая попытка логируется: `orders.attempt_number` инкрементируется, `orders.error_message` обновляется
  - Пользователь уведомляется: «Возникла небольшая задержка, пробуем ещё раз ⏳»

- **Политика возврата (refund при исчерпании попыток)**:
  - Если все 3 попытки исчерпаны → автоматический возврат через ЮКасса Refund API
  - `orders.status` → `refunded`, `payments.status` → `refunded`, `payments.refund_id` заполняется
  - Пользователь получает сообщение: «К сожалению, не удалось сгенерировать видео. Средства возвращены на карту. Приносим извинения! Вы можете повторить заказ»
  - нужно дать возможность повторить тот заказ который был неудачен и по нему произошел возврат
  - Фоновая задача отслеживает статус возврата и подтверждает пользователю

- **Фоновый мониторинг заказов**:
  - Периодическая задача (каждые 2 минуты) проверяет «зависшие» заказы со статусом `generating_video` дольше 15 минут
  - Автоматически запускает retry или refund

- Ошибка оплаты: заказ остаётся в `pending_payment`, пользователь может повторить
- Одновременные заказы: пользователь может создавать новые, пока другие генерируются
- Невалидный текст: проверка длины
- Graceful shutdown: корректное завершение при SIGTERM, текущие retry не теряются (состояние в БД)

---

### Verification

- **Локально**: `docker compose up` → PostgreSQL + бот в polling mode → протестировать весь флоу через Telegram
- **Оплата**: тестовый аккаунт ЮКассы (тестовый режим, имитация оплаты)
- **AI генерация**: проверить 5+ промптов с разными поводами
- **ElevenLabs**: тестовый вызов TTS с реальным `voice_id`
- **RunPod**: тестовый запрос → проверить что видео приходит в чат
- **VK**: параллельно тестировать основные сценарии в VK боте
- **Edge cases**: двойное нажатие кнопок, отмена на любом этапе, `/start` в середине флоу

### Decisions

- **TTS вместо STS**: voice_service.py будет полностью переписан — вместо `speech_to_speech.convert()` используем `text_to_speech.convert()` с `voice_id` персонажа из БД
- **выбранная разработчиком модель через OpenRouter**: баланс цена/качество для генерации коротких текстов (~100 слов)
- **Персонажи + креативы в БД**: двухуровневая структура (персонаж → креативы/образы), гибкость добавления без деплоя, admin управляет напрямую через SQL/pgAdmin
- **Гарантия результата**: клиент всегда получает видео или автоматический возврат денег; до 3 retry-попыток перед refund
- **RunPod отправляет видео сам**: не нужен отдельный механизм получения видео с нашей стороны; для отслеживания статуса — polling RunPod API по `job_id`
- **vkbottle для VK**: наиболее зрелая async-библиотека для VK ботов на Python
- **Alembic для миграций**: стандартный подход для SQLAlchemy, нужен для prod-деплоя
