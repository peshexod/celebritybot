# Celebrity Speaking Bot

Бот для Telegram и VK, который помогает сгенерировать поздравительный видео-кружок с выбранным персонажем.

## Запуск локально

1. Скопируйте `.env.example` в `.env` и заполните ключи.
2. Запустите контейнеры:
   - `docker compose up --build`

В локальном режиме (`BOT_MODE=polling`) подтверждение оплаты работает через фоновую проверку статуса платежа (polling к API ЮKassa), без ручной кнопки и без обязательного публичного webhook.

## Миграции в контейнере

- Миграции накатываются автоматически при старте сервиса `bot`:
   - `docker compose up --build`
- Ручной запуск миграций:
   - `docker compose run --rm bot alembic upgrade head`

## Контент персонажей (macOS)

Храни контент в папке проекта:

- `media/characters/<slug>/preview.jpg` — превью персонажа
- `media/characters/<slug>/creative_01.jpg` и далее — образы персонажа

Пример для Mac:

- `/Users/<your-user>/src/celebrity-speaking-bot/media/characters/statham/preview.jpg`

Как заполнять персонажей и образы в БД:

1. Скопируй шаблон каталога:
   - `cp media/characters/catalog.example.json media/characters/catalog.json`
2. Заполни `media/characters/catalog.json` своими данными и путями.
3. Прогони импорт (upsert):
   - в контейнере: `docker compose run --rm bot python scripts/seed_characters.py`
   - локально: `python scripts/seed_characters.py`

Скрипт обновляет существующего персонажа по `name` и добавляет/обновляет образы по `label`.

## Тесты

- Локально: `pytest -q`
- В контейнере (по необходимости): `docker compose run --rm bot pytest -q`

## CI/CD деплой (GitHub Actions)

Workflow в `.github/workflows/ci-cd.yml`:

- прогоняет lint + tests,
- собирает и пушит образ в GHCR: `ghcr.io/<owner>/<repo>` (через стандартный `GITHUB_TOKEN`),
- деплоит на сервер по SSH и запускает `docker compose -f docker-compose.prod.yml up -d`.

Для деплоя добавьте Secrets в GitHub репозитории:

- `SERVER_HOST` — IP/домен сервера
- `SERVER_USER` — SSH-пользователь
- `SERVER_SSH_KEY` — приватный SSH-ключ
- `SERVER_PORT` — SSH-порт (опционально, по умолчанию `22`)
- `DEPLOY_PATH` — путь на сервере, где лежит проект и `docker-compose.prod.yml`
- `SERVER_NAME` — доменное имя сервера (используется для `WEBHOOK_HOST=https://<SERVER_NAME>`)

## Режимы

- `BOT_MODE=polling` — локальная разработка, оплата подтверждается фоновой проверкой API ЮKassa
- `BOT_MODE=webhook` — прод, оплата подтверждается webhook от ЮKassa (`/webhook/yookassa`)

## Статусы заказа

- `pending_payment`
- `paid`
- `generating_audio`
- `generating_video`
- `retrying`
- `completed`
- `failed`
- `refunded`
