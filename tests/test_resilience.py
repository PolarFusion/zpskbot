import pytest
from datetime import date

from bot.handlers import build_router
from services.analytics_service import AnalyticsService


class _DummyMessageRepo:
    async def get_messages_for_period(self, chat_id, start, end):
        return [{"text": "msg?"}]

    async def get_activity_stats(self, chat_id, start, end):
        return [{"username": "alice", "msg_count": 1}]


class _RecordingSummaryRepo:
    def __init__(self):
        self.last_summary_text = None

    async def upsert_summary(self, **kwargs):
        self.last_summary_text = kwargs["summary_text"]


class _FailingLLM:
    async def generate_reply(self, context, user_input, chat_meta=None):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_analytics_daily_summary_fallback_on_llm_error():
    summary_repo = _RecordingSummaryRepo()
    svc = AnalyticsService(_DummyMessageRepo(), summary_repo, _FailingLLM())
    payload = await svc.build_daily_summary(chat_id=1, target_date=date(2026, 5, 14))
    assert "Не удалось собрать сводку" in payload["summary_text"]
    assert summary_repo.last_summary_text == payload["summary_text"]


@pytest.mark.asyncio
async def test_analytics_weekly_summary_fallback_on_llm_error():
    summary_repo = _RecordingSummaryRepo()
    svc = AnalyticsService(_DummyMessageRepo(), summary_repo, _FailingLLM())
    payload = await svc.build_weekly_summary(chat_id=1, end_date=date(2026, 5, 14))
    assert "Не удалось собрать сводку" in payload["summary_text"]
    assert summary_repo.last_summary_text == payload["summary_text"]


class _DummyTrackedChatRepo:
    async def track_chat(self, chat_id):
        return None


class _DummyMemoryService:
    def __init__(self):
        self.calls = []

    async def store_message_with_embedding(self, **kwargs):
        self.calls.append(kwargs)
        return 1

    async def retrieve_relevant(self, chat_id, query, limit=5):
        return [{"role": "user", "text": "ctx"}]

    @staticmethod
    def build_context_messages(messages, max_chars=3000):
        return [{"role": "user", "content": "ctx"}]


class _DummyAnalyticsService:
    async def build_daily_summary(self, chat_id, target_date):
        return {"summary_text": "ok"}

    async def get_stats(self, chat_id, days=7):
        return []

    async def get_topics(self, chat_id, days=7):
        return []


class _FailingReplyLLM:
    async def generate_reply(self, context, user_input, chat_meta=None):
        raise RuntimeError("llm down")


class _DummyUser:
    id = 42
    username = "tester"


class _DummyChat:
    id = 1001
    type = "private"


class _Sent:
    message_id = 2
    chat = _DummyChat()


class _DummyMessage:
    def __init__(self):
        self.from_user = _DummyUser()
        self.chat = _DummyChat()
        self.text = "hello"
        self.message_id = 1
        self.answers = []

    async def answer(self, text):
        self.answers.append(text)
        return _Sent()


@pytest.mark.asyncio
async def test_handler_on_message_fallback_on_llm_error():
    memory = _DummyMemoryService()
    router = build_router(
        llm_service=_FailingReplyLLM(),
        memory_service=memory,
        analytics_service=_DummyAnalyticsService(),
        tracked_chat_repo=_DummyTrackedChatRepo(),
        admin_ids=set(),
        bot_username="mybot",
        max_user_message_chars=4000,
        max_embedding_chars=2000,
    )
    on_message_handler = router.observers["message"].handlers[-1].callback
    msg = _DummyMessage()
    await on_message_handler(msg)

    assert msg.answers
    assert "временная перегрузка ИИ-сервиса" in msg.answers[0]


class _CaptureLLM:
    async def generate_reply(self, context, user_input, chat_meta=None):
        return "ok"


@pytest.mark.asyncio
async def test_handler_on_message_applies_user_and_embedding_limits():
    memory = _DummyMemoryService()
    router = build_router(
        llm_service=_CaptureLLM(),
        memory_service=memory,
        analytics_service=_DummyAnalyticsService(),
        tracked_chat_repo=_DummyTrackedChatRepo(),
        admin_ids=set(),
        bot_username="mybot",
        max_user_message_chars=5,
        max_embedding_chars=3,
    )
    on_message_handler = router.observers["message"].handlers[-1].callback
    msg = _DummyMessage()
    msg.text = "abcdefghi"
    await on_message_handler(msg)

    first_call = memory.calls[0]
    assert first_call["text"] == "abcde"
    assert first_call["embedding_input"] == "abc"


@pytest.mark.asyncio
async def test_handler_on_message_ignores_whitespace_only_text():
    memory = _DummyMemoryService()
    router = build_router(
        llm_service=_CaptureLLM(),
        memory_service=memory,
        analytics_service=_DummyAnalyticsService(),
        tracked_chat_repo=_DummyTrackedChatRepo(),
        admin_ids=set(),
        bot_username="mybot",
        max_user_message_chars=4000,
        max_embedding_chars=2000,
    )
    on_message_handler = router.observers["message"].handlers[-1].callback
    msg = _DummyMessage()
    msg.text = "   "
    await on_message_handler(msg)

    assert memory.calls == []
