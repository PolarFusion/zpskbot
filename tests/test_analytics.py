import pytest

from services.analytics_service import AnalyticsService


class DummyMessageRepo:
    async def get_messages_for_period(self, chat_id, start, end):
        return [
            {"text": "Как подключить оплату?"},
            {"text": "Оплата и подписка не работает"},
            {"text": "Нужен отчет по продажам"},
        ]

    async def get_activity_stats(self, chat_id, start, end):
        return [{"username": "alice", "msg_count": 10}]


class DummySummaryRepo:
    async def upsert_summary(self, **kwargs):
        return None


class DummyLLM:
    async def generate_reply(self, context, user_input, chat_meta=None):
        return "summary"


@pytest.mark.asyncio
async def test_topics_generated():
    svc = AnalyticsService(DummyMessageRepo(), DummySummaryRepo(), DummyLLM())
    topics = await svc.get_topics(chat_id=1, days=7)
    assert topics
    assert any(t[0] == "оплата" for t in topics)
