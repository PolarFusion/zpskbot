from __future__ import annotations

from typing import Any

from db.repositories import EmbeddingRepository, MessageRepository
from services.llm_service import LLMService


class MemoryService:
    def __init__(
        self,
        message_repo: MessageRepository,
        embedding_repo: EmbeddingRepository,
        llm_service: LLMService,
    ) -> None:
        self.message_repo = message_repo
        self.embedding_repo = embedding_repo
        self.llm_service = llm_service

    async def store_message_with_embedding(
        self,
        tg_message_id: int,
        chat_id: int,
        user_id: int,
        username: str | None,
        role: str,
        text: str,
        is_topic_question: bool,
        meta: dict[str, Any] | None = None,
        embedding_input: str | None = None,
    ) -> int:
        message_id = await self.message_repo.create_message(
            tg_message_id=tg_message_id,
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            role=role,
            text=text,
            is_topic_question=is_topic_question,
            meta=meta,
        )
        embedding_source = (embedding_input or text).strip() or "."
        embedding = await self.llm_service.create_embedding(embedding_source)
        await self.embedding_repo.create_embedding(message_id, chat_id, embedding)
        return message_id

    async def retrieve_relevant(self, chat_id: int, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query_embedding = await self.llm_service.create_embedding(query)
        candidate_ids = await self.embedding_repo.search_similar(chat_id, query_embedding, limit=limit)
        relevant = await self.message_repo.get_messages_by_ids(chat_id, candidate_ids)
        if relevant:
            return relevant
        return await self.message_repo.get_recent_messages(chat_id, limit=limit)

    @staticmethod
    def build_context_messages(messages: list[dict[str, Any]], max_chars: int = 3000) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        used = 0

        for m in reversed(messages):
            text = str(m.get("text") or "").strip()
            role = "assistant" if m.get("role") == "assistant" else "user"
            if not text:
                continue
            if used + len(text) > max_chars:
                break
            out.append({"role": role, "content": text})
            used += len(text)
        return out
