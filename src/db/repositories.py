from __future__ import annotations

import json
from datetime import date
from typing import Any

from db.database import Database


class MessageRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create_message(
        self,
        tg_message_id: int,
        chat_id: int,
        user_id: int,
        username: str | None,
        role: str,
        text: str,
        is_topic_question: bool,
        meta: dict[str, Any] | None = None,
    ) -> int:
        row = await self.db.fetchrow(
            """
            INSERT INTO messages (tg_message_id, chat_id, user_id, username, role, text, is_topic_question, meta)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
            RETURNING id
            """,
            tg_message_id,
            chat_id,
            user_id,
            username,
            role,
            text,
            is_topic_question,
            json.dumps(meta or {}),
        )
        if not row:
            raise RuntimeError("Failed to insert message")
        return int(row["id"])

    async def get_recent_messages(self, chat_id: int, limit: int = 15) -> list[dict[str, Any]]:
        rows = await self.db.fetch(
            """
            SELECT id, role, text, user_id, username, created_at
            FROM messages
            WHERE chat_id = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            chat_id,
            limit,
        )
        return [dict(r) for r in rows]

    async def get_messages_by_ids(self, chat_id: int, message_ids: list[int]) -> list[dict[str, Any]]:
        if not message_ids:
            return []

        rows = await self.db.fetch(
            """
            SELECT id, role, text, user_id, username, created_at
            FROM messages
            WHERE chat_id = $1
              AND id = ANY($2::bigint[])
            """,
            chat_id,
            message_ids,
        )
        by_id = {int(r["id"]): dict(r) for r in rows}
        return [by_id[mid] for mid in message_ids if mid in by_id]

    async def get_messages_for_period(self, chat_id: int, start: date, end: date) -> list[dict[str, Any]]:
        rows = await self.db.fetch(
            """
            SELECT id, user_id, username, text, created_at
            FROM messages
            WHERE chat_id = $1
              AND created_at::date >= $2
              AND created_at::date <= $3
            ORDER BY created_at ASC
            """,
            chat_id,
            start,
            end,
        )
        return [dict(r) for r in rows]

    async def get_activity_stats(self, chat_id: int, start: date, end: date) -> list[dict[str, Any]]:
        rows = await self.db.fetch(
            """
            SELECT user_id, COALESCE(username, 'unknown') AS username, COUNT(*) AS msg_count
            FROM messages
            WHERE chat_id = $1
              AND created_at::date >= $2
              AND created_at::date <= $3
            GROUP BY user_id, username
            ORDER BY msg_count DESC
            LIMIT 20
            """,
            chat_id,
            start,
            end,
        )
        return [dict(r) for r in rows]


class EmbeddingRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create_embedding(self, message_id: int, chat_id: int, embedding: list[float]) -> None:
        vector_literal = "[" + ",".join(str(x) for x in embedding) + "]"
        await self.db.execute(
            """
            INSERT INTO embeddings (message_id, chat_id, embedding)
            VALUES ($1, $2, $3::vector)
            """,
            message_id,
            chat_id,
            vector_literal,
        )

    async def search_similar(self, chat_id: int, embedding: list[float], limit: int = 5) -> list[int]:
        vector_literal = "[" + ",".join(str(x) for x in embedding) + "]"
        rows = await self.db.fetch(
            """
            SELECT message_id
            FROM embeddings
            WHERE chat_id = $1
            ORDER BY embedding <-> $2::vector
            LIMIT $3
            """,
            chat_id,
            vector_literal,
            limit,
        )
        return [int(r["message_id"]) for r in rows]


class SummaryRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def upsert_summary(
        self,
        chat_id: int,
        period_type: str,
        period_start: date,
        period_end: date,
        summary_text: str,
        payload: dict[str, Any],
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO summaries (chat_id, period_type, period_start, period_end, summary_text, payload)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            ON CONFLICT (chat_id, period_type, period_start, period_end)
            DO UPDATE SET summary_text = EXCLUDED.summary_text, payload = EXCLUDED.payload, created_at = NOW()
            """,
            chat_id,
            period_type,
            period_start,
            period_end,
            summary_text,
            json.dumps(payload),
        )

    async def get_latest_summary(self, chat_id: int, period_type: str) -> dict[str, Any] | None:
        row = await self.db.fetchrow(
            """
            SELECT summary_text, payload, period_start, period_end, created_at
            FROM summaries
            WHERE chat_id = $1 AND period_type = $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            chat_id,
            period_type,
        )
        return dict(row) if row else None


class TrackedChatRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def track_chat(self, chat_id: int) -> None:
        await self.db.execute(
            """
            INSERT INTO tracked_chats (chat_id)
            VALUES ($1)
            ON CONFLICT (chat_id) DO NOTHING
            """,
            chat_id,
        )

    async def list_tracked_chat_ids(self) -> list[int]:
        rows = await self.db.fetch("SELECT chat_id FROM tracked_chats ORDER BY created_at ASC")
        return [int(r["chat_id"]) for r in rows]
