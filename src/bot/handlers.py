from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.access import is_admin, should_respond_in_group
from db.repositories import TrackedChatRepository
from services.analytics_service import AnalyticsService
from services.llm_service import LLMService
from services.memory_service import MemoryService

logger = logging.getLogger(__name__)


def build_router(
    llm_service: LLMService,
    memory_service: MemoryService,
    analytics_service: AnalyticsService,
    tracked_chat_repo: TrackedChatRepository,
    admin_ids: set[int],
    bot_username: str,
    max_user_message_chars: int,
    max_embedding_chars: int,
) -> Router:
    router = Router()

    async def ensure_admin(message: Message) -> bool:
        user_id = message.from_user.id if message.from_user else 0
        if not is_admin(user_id, admin_ids):
            await message.answer("Эта команда доступна только админам.")
            return False
        return True

    async def track_chat(message: Message) -> None:
        await tracked_chat_repo.track_chat(message.chat.id)

    @router.message(Command("start"))
    async def cmd_start(message: Message) -> None:
        await message.answer("Привет. Я ИИ-бот для группы и лички: отвечаю на вопросы и делаю аналитику чата.")

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(
            "Команды:\n"
            "/summary - сводка за день\n"
            "/stats - активность участников\n"
            "/topics - топ-темы\n"
            "В группе отвечаю по упоминанию, реплаю или команде."
        )

    @router.message(Command("summary"))
    async def cmd_summary(message: Message) -> None:
        if not await ensure_admin(message):
            return

        await track_chat(message)
        payload = await analytics_service.build_daily_summary(message.chat.id, datetime.now(timezone.utc).date())
        await message.answer(payload["summary_text"])

    @router.message(Command("stats"))
    async def cmd_stats(message: Message) -> None:
        if not await ensure_admin(message):
            return

        await track_chat(message)
        stats = await analytics_service.get_stats(message.chat.id, days=7)
        if not stats:
            await message.answer("Недостаточно данных для статистики.")
            return

        lines = ["Активность за 7 дней:"]
        for row in stats[:10]:
            lines.append(f"- @{row['username']}: {row['msg_count']} сообщений")
        await message.answer("\n".join(lines))

    @router.message(Command("topics"))
    async def cmd_topics(message: Message) -> None:
        if not await ensure_admin(message):
            return

        await track_chat(message)
        topics = await analytics_service.get_topics(message.chat.id, days=7)
        if not topics:
            await message.answer("Недостаточно данных для тем.")
            return

        lines = ["Топ тем за 7 дней:"]
        for topic, count in topics:
            lines.append(f"- {topic}: {count}")
        await message.answer("\n".join(lines))

    @router.message(F.text)
    async def on_message(message: Message) -> None:
        if not message.from_user or not message.text:
            return

        if message.chat.type in {"group", "supergroup"}:
            if not should_respond_in_group(message, bot_username):
                return

        await track_chat(message)

        user_text = message.text.strip()[:max_user_message_chars]
        if not user_text:
            return
        embedding_text = user_text[:max_embedding_chars]
        await memory_service.store_message_with_embedding(
            tg_message_id=message.message_id,
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            username=message.from_user.username,
            role="user",
            text=user_text,
            is_topic_question="?" in user_text,
            meta={"chat_type": message.chat.type},
            embedding_input=embedding_text,
        )

        relevant = await memory_service.retrieve_relevant(message.chat.id, user_text, limit=5)
        context = memory_service.build_context_messages(relevant, max_chars=2800)

        try:
            reply_text = await llm_service.generate_reply(
                context=context,
                user_input=user_text,
                chat_meta={"chat_id": message.chat.id, "chat_type": message.chat.type},
            )
        except Exception:
            logger.exception("Failed to generate LLM reply", extra={"chat_id": message.chat.id})
            reply_text = "Сейчас временная перегрузка ИИ-сервиса. Попробуй еще раз через минуту."

        sent = await message.answer(reply_text)

        await memory_service.store_message_with_embedding(
            tg_message_id=sent.message_id,
            chat_id=sent.chat.id,
            user_id=0,
            username=bot_username,
            role="assistant",
            text=reply_text,
            is_topic_question=False,
            meta={"reply_to": message.message_id},
        )

    return router
