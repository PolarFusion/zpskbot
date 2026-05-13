from __future__ import annotations

from db.database import Database


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    tg_message_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    is_topic_question BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    meta JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages (chat_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS embeddings (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_chat ON embeddings (chat_id);

CREATE TABLE IF NOT EXISTS summaries (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    period_type TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    summary_text TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chat_id, period_type, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS tracked_chats (
    chat_id BIGINT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def init_schema(db: Database) -> None:
    await db.execute(SCHEMA_SQL)
