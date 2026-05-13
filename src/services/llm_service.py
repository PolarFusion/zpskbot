from __future__ import annotations

import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


SYSTEM_PROMPT = (
    "Ты ИИ-помощник Telegram-сообщества. Отвечай по-русски, кратко и полезно. "
    "Если данных не хватает, задай уточняющий вопрос. Будь дружелюбным и конкретным."
)

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(self, api_key: str, model: str, base_url: str, embedding_model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.embedding_model = embedding_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def generate_reply(
        self,
        context: list[dict[str, str]],
        user_input: str,
        chat_meta: dict[str, Any] | None = None,
    ) -> str:
        chat_meta = chat_meta or {}
        input_messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if chat_meta:
            input_messages.append(
                {
                    "role": "system",
                    "content": f"Контекст чата: {chat_meta}",
                }
            )

        input_messages.extend(context)
        input_messages.append({"role": "user", "content": user_input})

        response = await asyncio.wait_for(
            self.client.responses.create(
                model=self.model,
                input=input_messages,
                temperature=0.4,
            ),
            timeout=25,
        )
        output = (response.output_text or "").strip()
        if not output:
            logger.warning("LLM returned empty output", extra={"model": self.model, "chat_meta": chat_meta})
            return "Не смог сформировать ответ, попробуй перефразировать вопрос."
        return output

    async def create_embedding(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(model=self.embedding_model, input=text)
        return response.data[0].embedding
