from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any

from db.repositories import MessageRepository, SummaryRepository
from services.llm_service import LLMService

STOP_WORDS = {
    "и", "в", "на", "с", "а", "по", "к", "у", "за", "не", "что", "как", "это", "но", "или", "из", "для"
}
logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(
        self,
        message_repo: MessageRepository,
        summary_repo: SummaryRepository,
        llm_service: LLMService,
    ) -> None:
        self.message_repo = message_repo
        self.summary_repo = summary_repo
        self.llm_service = llm_service

    async def build_daily_summary(self, chat_id: int, target_date: date) -> dict[str, Any]:
        messages = await self.message_repo.get_messages_for_period(chat_id, target_date, target_date)
        stats = await self.message_repo.get_activity_stats(chat_id, target_date, target_date)
        payload = self._build_payload(messages, stats)

        summary_prompt = self._make_summary_prompt(payload, period_label=f"день {target_date.isoformat()}")
        summary_text = await self._generate_summary_with_fallback(
            summary_prompt=summary_prompt,
            log_message="Failed to generate daily summary",
            log_extra={"chat_id": chat_id, "date": target_date.isoformat()},
        )
        await self._save_summary(
            chat_id=chat_id,
            period_type="daily",
            period_start=target_date,
            period_end=target_date,
            summary_text=summary_text,
            payload=payload,
        )
        payload["summary_text"] = summary_text
        return payload

    async def build_weekly_summary(self, chat_id: int, end_date: date | None = None) -> dict[str, Any]:
        end_date = end_date or datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=6)
        messages = await self.message_repo.get_messages_for_period(chat_id, start_date, end_date)
        stats = await self.message_repo.get_activity_stats(chat_id, start_date, end_date)
        payload = self._build_payload(messages, stats)

        summary_prompt = self._make_summary_prompt(
            payload,
            period_label=f"неделя {start_date.isoformat()} - {end_date.isoformat()}",
        )
        summary_text = await self._generate_summary_with_fallback(
            summary_prompt=summary_prompt,
            log_message="Failed to generate weekly summary",
            log_extra={"chat_id": chat_id, "start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        )
        await self._save_summary(
            chat_id=chat_id,
            period_type="weekly",
            period_start=start_date,
            period_end=end_date,
            summary_text=summary_text,
            payload=payload,
        )
        payload["summary_text"] = summary_text
        return payload

    async def get_topics(self, chat_id: int, days: int = 7) -> list[tuple[str, int]]:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=max(1, days - 1))
        messages = await self.message_repo.get_messages_for_period(chat_id, start_date, end_date)
        counter: Counter[str] = Counter()

        for m in messages:
            for token in self._tokenize(m.get("text", "")):
                counter[token] += 1

        return counter.most_common(10)

    async def get_stats(self, chat_id: int, days: int = 7) -> list[dict[str, Any]]:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=max(1, days - 1))
        return await self.message_repo.get_activity_stats(chat_id, start_date, end_date)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        raw = [w.strip(".,!?()[]{}:;\"'`).-_/").lower() for w in text.split()]
        return [w for w in raw if len(w) > 3 and w not in STOP_WORDS]

    def _build_payload(self, messages: list[dict[str, Any]], stats: list[dict[str, Any]]) -> dict[str, Any]:
        questions = [m["text"] for m in messages if "?" in str(m.get("text", ""))][:15]
        topic_counter: Counter[str] = Counter()
        for m in messages:
            for token in self._tokenize(str(m.get("text", ""))):
                topic_counter[token] += 1

        return {
            "message_count": len(messages),
            "top_users": stats[:10],
            "top_topics": topic_counter.most_common(10),
            "top_questions": questions,
        }

    @staticmethod
    def _make_summary_prompt(payload: dict[str, Any], period_label: str) -> str:
        return (
            f"Сделай краткую аналитическую сводку за {period_label}. "
            f"Сообщений: {payload['message_count']}. "
            f"Топ темы: {payload['top_topics']}. "
            f"Топ участники: {payload['top_users']}. "
            f"Важные вопросы: {payload['top_questions']}. "
            "Формат: 1) главное, 2) тренды, 3) риски/пробелы, 4) рекомендации."
        )

    async def _generate_summary_with_fallback(
        self,
        summary_prompt: str,
        log_message: str,
        log_extra: dict[str, Any],
    ) -> str:
        try:
            return await self.llm_service.generate_reply(
                context=[],
                user_input=summary_prompt,
                chat_meta={"mode": "summary"},
            )
        except Exception:
            logger.exception(log_message, extra=log_extra)
            return "Не удалось собрать сводку из-за временной ошибки ИИ-сервиса."

    async def _save_summary(
        self,
        chat_id: int,
        period_type: str,
        period_start: date,
        period_end: date,
        summary_text: str,
        payload: dict[str, Any],
    ) -> None:
        await self.summary_repo.upsert_summary(
            chat_id=chat_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            summary_text=summary_text,
            payload=payload,
        )
