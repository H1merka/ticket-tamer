# Ticket Tamer

AI-агент для автоматизации обработки писем технической поддержки компании [ЭРИС](https://eriskip.com) (производитель газоаналитического оборудования).  
Проект разработан в рамках хакатона **ENIGMA HACK 2026**.

## Возможности

- Автоматический приём входящих email по IMAP (polling каждые 60 сек)
- Классификация обращений по 5 категориям ЭРИС (неисправность, калибровка, документация, доступ к ПО, прочее) с анализом тональности
- Извлечение сущностей (NER): ФИО, организация, телефон, заводские номера, тип устройства
- RAG-поиск по базе знаний с pgvector (двухфазный поиск + LLM-реранкинг)
- Автоматическая генерация ответа на основе KB-контекста
- Отправка ответа клиенту по SMTP (при confidence ≥ 0.7) или маркировка для ручной проверки
- Парсинг вложений: PDF, DOCX, изображения (OCR), аудио (Whisper)
- Web-краулер eriskip.com для автоматического наполнения базы знаний
- Уведомления в Telegram и синхронизация с Google Sheets
- Веб-интерфейс: таблица тикетов с фильтрацией/сортировкой, дашборд аналитики, экспорт CSV/XLSX
- JWT-аутентификация

## Стек технологий

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.10, FastAPI, SQLAlchemy 2.0 (async), APScheduler |
| База данных | PostgreSQL 16 + pgvector (HNSW-индексы, 1024-dim) |
| LLM / Embeddings | OpenAI-совместимый API через [RouterAI](https://routerai.ru) — deepseek-v3.2, bge-m3 |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Radix UI, Recharts |
| Auth | JWT (python-jose + passlib/bcrypt) |
| Email | aioimaplib (IMAP), aiosmtplib (SMTP) |
| Деплой | Docker multi-stage build, Docker Compose |

## Архитектура

```
Клиент (Email)
      │
      ▼
┌─────────────┐    ┌──────────────────────┐    ┌──────────────────┐
│  IMAP-слой  │───▶│      AI-агент        │───▶│   База знаний    │
│  (приём)    │    │  (classification,    │    │   (pgvector)     │
└─────────────┘    │   NER, RAG, генера-  │    └──────────────────┘
                   │   ция ответа)        │
                   └──────────┬───────────┘
                              │
                   ┌──────────▼───────────┐
                   │     PostgreSQL       │
                   │   (тикеты, логи)     │
                   └──────────┬───────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      ┌────────────┐  ┌────────────┐  ┌─────────────┐
      │  Веб-UI    │  │ SMTP-слой  │  │  Telegram / │
      │  (React)   │  │ (отправка) │  │  Sheets     │
      └────────────┘  └────────────┘  └─────────────┘
```

### Пайплайн AI-агента

Каждый шаг — отдельный модуль в `agent/`, может быть заменён независимо:

```
Входящее письмо
  → 0. Парсинг вложений (PDF/DOCX/OCR/Whisper)
  → 1. Классификация (категория, приоритет, тональность)
  → 2. Извлечение сущностей (NER через LLM JSON-mode)
  → 3. RAG-поиск по базе знаний (embed → vector search → LLM rerank → top-3)
  → 4. Генерация ответа (LLM с KB-контекстом)
  → 5. Сохранение тикета в БД
  → 6. Отправка ответа по SMTP
  → 7. Индексация Q&A обратно в KB
  → 8. Уведомление Telegram + Google Sheets
```

## Структура проекта

```
ticket-tamer/
├── app/                        # FastAPI backend
│   ├── main.py                 # Точка входа, lifespan, middleware, SPA-fallback
│   ├── config.py               # Pydantic Settings из .env
│   ├── database.py             # Async SQLAlchemy engine + session
│   ├── dependencies.py         # DI: get_db, get_current_user
│   ├── models/                 # ORM-модели
│   │   ├── ticket.py           # Тикеты
│   │   ├── knowledge_base.py   # Статьи базы знаний
│   │   ├── kb_chunk.py         # Векторные чанки (pgvector)
│   │   ├── email_log.py        # Лог email-операций
│   │   └── user.py             # Пользователи
│   ├── schemas/                # Pydantic request/response
│   ├── routers/                # API endpoints
│   │   ├── tickets.py          # CRUD тикетов
│   │   ├── knowledge_base.py   # KB + загрузка файлов
│   │   ├── analytics.py        # Summary и timeline
│   │   ├── export.py           # CSV / XLSX
│   │   └── auth.py             # Login, register, me
│   └── services/               # Бизнес-логика
│       ├── email_service.py    # IMAP polling, SMTP sending
│       ├── kb_service.py       # Управление базой знаний
│       ├── kb_cleanup_service.py # Ротация устаревших записей
│       ├── sheets_service.py   # Синхронизация с Google Sheets
│       └── telegram_service.py # Telegram-уведомления
├── agent/                      # AI-агент (изолирован от web-слоя)
│   ├── pipeline.py             # Оркестратор полного пайплайна
│   ├── classifier.py           # LLM-классификация
│   ├── entity_extractor.py     # NER через LLM
│   ├── kb_lookup.py            # Двухфазный RAG-поиск + реранкинг
│   ├── response_generator.py   # Генерация ответа
│   ├── llm_client.py           # Singleton OpenAI-клиент с retry и fallback
│   ├── indexer.py              # Чанкинг + эмбеддинг документов
│   ├── crawler.py              # Краулер eriskip.com
│   ├── attachment_parser.py    # PDF, DOCX, OCR, аудио
│   ├── audio_transcriber.py    # Whisper API
│   └── product_parser.py       # Парсинг страниц продуктов
├── frontend/                   # React + Vite + TypeScript
│   └── src/
│       ├── pages/              # Dashboard, Messages, Login
│       ├── components/         # UI-компоненты (shadcn/Radix)
│       ├── api/client.ts       # HTTP-клиент с JWT
│       ├── context/            # AuthContext
│       └── types/              # TypeScript типы
├── migrations/                 # Alembic-миграции
├── docker-compose.yml          # PostgreSQL (pgvector) + backend
├── Dockerfile                  # Multi-stage: Node (фронт) → Python (бэк)
├── requirements.txt            # Python-зависимости
└── alembic.ini                 # Настройки Alembic
```

## Запуск

### Docker (рекомендуется)

```bash
# Создать файл .env (см. раздел «Переменные окружения»)
cp .env.example .env

# Запустить все сервисы
docker compose up --build
```

Приложение будет доступно по адресу `http://localhost:8000`.  
Миграции БД применяются автоматически при старте контейнера.

### Локальная разработка

**Требования:** Python 3.10+, Node.js 20+, PostgreSQL 16 с расширением pgvector, Tesseract OCR.

```bash
# Backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS
pip install -r requirements.txt

alembic upgrade head
uvicorn app.main:app --reload
```

```bash
# Frontend (в отдельном терминале)
cd frontend
npm install
npm run dev
```

## Переменные окружения

Создайте файл `.env` в корне проекта. Обязательные переменные отмечены `*`:

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `DATABASE_URL` * | Строка подключения PostgreSQL | `postgresql+asyncpg://postgres:postgres@localhost:5432/ticket_tamer` |
| `ROUTERAI_API_KEY` * | API-ключ RouterAI для LLM/Embeddings | — |
| `IMAP_HOST` | IMAP-сервер | `imap.example.com` |
| `IMAP_PORT` | Порт IMAP | `993` |
| `IMAP_USER` | Логин IMAP | — |
| `IMAP_PASSWORD` | Пароль IMAP | — |
| `SMTP_HOST` | SMTP-сервер | `smtp.example.com` |
| `SMTP_PORT` | Порт SMTP | `587` |
| `SMTP_USER` | Логин SMTP | — |
| `SMTP_PASSWORD` | Пароль SMTP | — |
| `JWT_SECRET_KEY` * | Секрет для подписи JWT-токенов | — |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота | — |
| `TELEGRAM_CHAT_ID` | ID чата для уведомлений | — |
| `GOOGLE_SHEETS_CREDENTIALS_FILE` | Путь к JSON-ключу сервисного аккаунта | — |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | ID таблицы Google Sheets | — |

## API

Все эндпоинты (кроме `/health` и авторизации) требуют JWT-токен в заголовке `Authorization: Bearer <token>`.

| Метод | Путь | Описание |
|-------|------|---------|
| `POST` | `/api/v1/auth/register` | Регистрация пользователя |
| `POST` | `/api/v1/auth/login` | Авторизация, получение JWT |
| `GET` | `/api/v1/auth/me` | Информация о текущем пользователе |
| `GET` | `/api/v1/tickets/` | Список тикетов (фильтрация, пагинация) |
| `GET` | `/api/v1/tickets/{id}` | Детали тикета |
| `POST` | `/api/v1/tickets/` | Создание тикета |
| `PATCH` | `/api/v1/tickets/{id}` | Обновление тикета |
| `GET` | `/api/v1/kb/` | Список статей базы знаний |
| `POST` | `/api/v1/kb/` | Создание статьи KB |
| `POST` | `/api/v1/kb/index` | Загрузка и индексация файла в KB |
| `GET` | `/api/v1/analytics/summary` | Сводка по тикетам |
| `GET` | `/api/v1/analytics/timeline` | Тикеты по дням |
| `GET` | `/api/v1/export/csv` | Экспорт тикетов в CSV |
| `GET` | `/api/v1/export/xlsx` | Экспорт тикетов в XLSX |
| `GET` | `/health` | Проверка состояния сервиса |

Полная документация API доступна по адресу `/docs` (Swagger UI) после запуска сервера.

## Лицензия

[MIT](LICENSE) — Morgenshtern Dmitrij, 2026