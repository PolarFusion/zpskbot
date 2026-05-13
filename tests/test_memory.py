from services.memory_service import MemoryService


def test_build_context_messages_limits_size():
    messages = [
        {"role": "user", "text": "a" * 500},
        {"role": "assistant", "text": "b" * 500},
        {"role": "user", "text": "c" * 500},
    ]
    out = MemoryService.build_context_messages(messages, max_chars=900)

    total = sum(len(item["content"]) for item in out)
    assert total <= 900
    assert all(item["role"] in {"user", "assistant"} for item in out)


class _DummyLLM:
    async def create_embedding(self, text):
        return [0.1, 0.2]


class _DummyEmbeddingRepo:
    async def search_similar(self, chat_id, embedding, limit=5):
        return [30, 10]


class _DummyMessageRepo:
    async def get_messages_by_ids(self, chat_id, message_ids):
        return [
            {"id": 30, "role": "assistant", "text": "thirty"},
            {"id": 10, "role": "user", "text": "ten"},
        ]

    async def get_recent_messages(self, chat_id, limit=5):
        return [{"id": 1, "role": "user", "text": "recent"}]


import pytest


@pytest.mark.asyncio
async def test_retrieve_relevant_uses_db_ids_order():
    svc = MemoryService(_DummyMessageRepo(), _DummyEmbeddingRepo(), _DummyLLM())
    out = await svc.retrieve_relevant(chat_id=1, query="hello", limit=2)
    assert [m["id"] for m in out] == [30, 10]
