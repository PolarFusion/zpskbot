# zpskbot

Telegram ИИ-бот для группы и лички с аналитикой сообщений.

## Возможности v1
- Ответы через OpenAI в личке и группе.
- В группе отвечает только по триггеру: упоминание, reply, команда.
- Команды админа: `/summary`, `/stats`, `/topics`.
- Память диалога: recent context + semantic retrieval через pgvector.
- Ежедневные и недельные сводки в фоне.

## Быстрый старт
1. Скопируй окружение:
```bash
cp .env.example .env
```
2. Заполни `.env`:
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL` (для OpenAI: `https://api.openai.com/v1`, для OpenRouter: `https://openrouter.ai/api/v1`)
- `OPENAI_EMBEDDING_MODEL` (по умолчанию `text-embedding-3-small`)
- `DATABASE_URL`
- `ADMIN_IDS` (через запятую)
- `BOT_USERNAME` (без `@`)
- `MAX_USER_MESSAGE_CHARS` (лимит длины входа, по умолчанию `4000`)
- `MAX_EMBEDDING_CHARS` (лимит длины текста для эмбеддинга, по умолчанию `2000`)

3. Запуск локально:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
python src/app.py
```

## PostgreSQL + pgvector
Убедись, что в БД установлен pgvector (бот также вызывает `CREATE EXTENSION IF NOT EXISTS vector`).

## Deploy на Render/Railway
- Используй `Dockerfile`.
- Для webhook:
  - `USE_WEBHOOK=true`
  - `WEBHOOK_BASE_URL=https://<your-domain>`
  - `WEBHOOK_PATH=/telegram/webhook`
- Для polling:
  - `USE_WEBHOOK=false`

## Команды
- `/start`
- `/help`
- `/summary` (admin)
- `/stats` (admin)
- `/topics` (admin)

## Production checklist Telegram
- Отключи лишние BotFather permissions, оставь нужные.
- В группе проверь privacy mode согласно сценарию.
- Добавь бота в админы, если нужны расширенные права.
- Проверь webhook URL и TLS.
- Задай `ADMIN_IDS` только доверенным user_id.

## Тесты
```bash
pytest -q
```
