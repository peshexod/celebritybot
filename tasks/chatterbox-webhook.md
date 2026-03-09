# Task: Интеграция Chatterbox + Sonic с webhook в celebritybot

## Суть
Заменить ElevenLabs на Chatterbox TTS и перевести генерацию на webhook-based асинхронный флоу.

## Текущее состояние (AS-IS)
- voice_service.py — синхронно использует ElevenLabs
- video_service.py — использует RunPod polling (delays [5, 15, 45])
- order_service.py — обрабатывает синхронно: audio → video
- Нет webhook эндпоинтов для асинхронных сервисов

## Решение (TO-BE)
1. Chatterbox webhook: при success → запускаем video
2. При error → ретраим audio (лимит попыток)
3. Sonic webhook: при success → отправляем результат
4. При error → ретраим video

---

## Пошаговый план

### Phase 1: Подготовка (инфраструктура)

#### 1.1 Config — добавить настройки
В `bot/config.py` добавить:
```python
runpod_chatterbox_endpoint: str = Field(default="", alias="RUNPOD_CHATTERBOX_ENDPOINT")
runpod_chatterbox_api_key: str = Field(default="", alias="RUNPOD_CHATTERBOX_API_KEY")  # или использовать существующий RUNPOD_API_KEY
```

#### 1.2 База данных — миграция
Создать Alembic миграцию `001_add_job_ids.py`:
```python
# Добавить колонки в orders table:
op.add_column('orders', sa.Column('chatterbox_job_id', sa.String(64), nullable=True))
op.add_column('orders', sa.Column('sonic_job_id', sa.String(64), nullable=True))
op.add_column('orders', sa.Column('video_file_id', sa.String(256), nullable=True))
op.add_column('orders', sa.Column('chatterbox_attempt', sa.Integer(), default=0))
op.add_column('orders', sa.Column('sonic_attempt', sa.Integer(), default=0))
```

#### 1.3 Models — обновить SQLAlchemy модели
В `bot/db/models.py` добавить поля в Order:
```python
chatterbox_job_id = Column(String(64), nullable=True)
sonic_job_id = Column(String(64), nullable=True)
video_file_id = Column(String(256), nullable=True)
chatterbox_attempt = Column(Integer, default=0)
sonic_attempt = Column(Integer, default=0)
```

#### 1.4 Repositories — добавить методы
В `bot/db/repositories/order_repo.py`:
- `set_chatterbox_job(order_id, job_id)`
- `set_sonic_job(order_id, job_id)`
- `set_video_file_id(order_id, file_id)`
- `increment_chatterbox_attempt(order_id)`
- `increment_sonic_attempt(order_id)`
- `get_order_by_chatterbox_job(job_id)`
- `get_order_by_sonic_job(job_id)`

---

### Phase 2: Сервисы (отправка job)

#### 2.1 ChatterboxService — новый класс
Создать `bot/services/chatterbox_service.py`:
```python
class ChatterboxService:
    def __init__(self):
        self.settings = get_settings()
    
    async def submit_job(
        self,
        text: str,
        voice_name: str,
        webhook_url: str,
    ) -> str:
        # POST /run на RunPod с webhook
        payload = {
            "input": {
                "text": text,
                "voice_name": voice_name,  # или voice_id
            },
            "webhook": {"url": webhook_url}
        }
        # ... отправка на runpod_chatterbox_endpoint
        return job_id
```

#### 2.2 VideoService — обновить
Добавить webhook_url в `video_service.py`:
```python
async def submit_job(..., webhook_url: str) -> str:
    payload = {
        "input": {...},
        "webhook": {"url": webhook_url}
    }
```

#### 2.3 Retry логика
Добавить методы retry:
```python
async def retry_audio(order_id: int, attempt: int) -> bool:
    MAX_ATTEMPTS = 3
    if attempt >= MAX_ATTEMPTS:
        return False
    # логика ретрая
    return True
```

---

### Phase 3: Webhook Handlers

#### 3.1 Добавить endpoints
В `bot/web/webhooks.py`:
```python
# POST /webhook/chatterbox
async def chatterbox_webhook(request: web.Request) -> web.Response:
    payload = await request.json()
    job_id = payload.get("id")
    output = payload.get("output", {})
    
    if output.get("error"):
        # Retry audio
        await retry_audio(order_id, attempt + 1)
    else:
        # Success - запустить video
        audio_base64 = output.get("audio_base64")
        await start_video_generation(order_id, audio_base64)
    
    return web.Response(text="ok")

# POST /webhook/sonic
async def sonic_webhook(request: web.Request) -> web.Response:
    payload = await request.json()
    job_id = payload.get("id")
    output = payload.get("output", {})
    
    if output.get("error"):
        # Retry video
        await retry_video(order_id, attempt + 1)
    else:
        # Success - отправить пользователю
        file_id = output.get("telegram_file_id")
        await send_result_to_user(order_id, file_id)
    
    return web.Response(text="ok")
```

#### 3.2 Регистрация роутов
```python
app.router.add_post("/webhook/chatterbox", chatterbox_webhook)
app.router.add_post("/webhook/sonic", sonic_webhook)
```

---

### Phase 4: Интеграция (изменение flow)

#### 4.1 Изменить yookassa_webhook
В `webhooks.py` при `payment.succeeded`:
- Не вызывать `process_paid_order` синхронно
- Вместо этого: создать заказ → запустить chatterbox job → сохранить chatterbox_job_id

#### 4.2 Изменить order_service
Убрать синхронный вызов audio/video:
- `process_paid_order()` → только создаёт заказ и запускает audio
- Завершение происходит в webhook handlers

#### 4.3 Отправка уведомлений
Добавить в webhook handlers:
- "🎤 Начинаю генерацию аудио..."
- "✅ Аудио готово, запускаю видео..."
- "🎬 Видео готово!"

---

### Phase 5: Тестирование

#### 5.1 Локальное тестирование
- Запустить бота в polling режиме
- Пройти полный flow до оплаты
- Проверить webhook через ngrok

#### 5.2 Integration тесты
- Проверить retry логику
- Проверить обработку ошибок
- Проверить уведомления

#### 5.3 Прод
- Деплой
- Мониторинг логов

---

## Технические детали

### Retry стратегия
- **Max attempts**: 3
- **Delays**: экспоненциальный backoff (опционально)
- При превышении max → `OrderStatus.failed`

### Webhook payload от RunPod
```json
{
  "id": "job_abc123",
  "status": "COMPLETED",
  "output": {
    "audio_base64": "...",
    "error": null
  }
}
```

### Конфиг .env
```
RUNPOD_CHATTERBOX_ENDPOINT=https://api.runpod.ai/v2/xxx/run
RUNPOD_CHATTERBOX_API_KEY=...
WEBHOOK_HOST=https://seleb.xyz
```

---

## Чеклист
- [ ] RUNPOD_CHATTERBOX_ENDPOINT добавлен в config
- [ ] Миграция создана и применена
- [ ] Колонки добавлены в БД
- [ ] ChatterboxService создан
- [ ] VideoService обновлён с webhook
- [ ] /webhook/chatterbox работает
- [ ] /webhook/sonic работает
- [ ] Retry логика работает
- [ ] video_file_id сохраняется в БД
- [ ] Пользователь получает уведомления
- [ ] Результат отправляется в чат
- [ ] Локально протестировано
- [ ] Задеплоено в прод
