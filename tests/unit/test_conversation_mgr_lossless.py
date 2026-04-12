from datetime import datetime, timezone

import pytest

from astrbot.core.conversation_mgr import ConversationManager
from astrbot.core.db.po import ConversationV2


class FakeDB:
    def __init__(self, conversation: ConversationV2 | None = None) -> None:
        self.conversation = conversation
        self.updated_payloads: list[dict] = []

    async def get_conversation_by_id(self, cid: str):
        if self.conversation and self.conversation.conversation_id == cid:
            return self.conversation
        return None

    async def update_conversation(
        self,
        cid: str,
        title=None,
        persona_id=None,
        content=None,
        token_usage=None,
    ) -> None:
        self.updated_payloads.append(
            {
                "cid": cid,
                "title": title,
                "persona_id": persona_id,
                "content": content,
                "token_usage": token_usage,
            },
        )
        if self.conversation and self.conversation.conversation_id == cid:
            if content is not None:
                self.conversation.content = content


class FakeLosslessStore:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, list[dict]]] = []

    async def ingest_messages(self, conversation_id: str, history: list[dict]) -> None:
        if self.should_fail:
            raise RuntimeError("boom")
        self.calls.append((conversation_id, history))


def _conversation(history: list[dict] | None = None) -> ConversationV2:
    now = datetime.now(timezone.utc)
    return ConversationV2(
        inner_conversation_id=1,
        conversation_id="conv-1",
        platform_id="qq",
        user_id="qq:group:1",
        content=history or [],
        title="Test",
        persona_id="default",
        token_usage=0,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_get_conversation_mirrors_history_into_lossless_store():
    db = FakeDB(_conversation([{"role": "user", "content": "你好"}]))
    store = FakeLosslessStore()
    manager = ConversationManager(db, lossless_store=store)

    conversation = await manager.get_conversation("qq:group:1", "conv-1")

    assert conversation is not None
    assert store.calls == [("conv-1", [{"role": "user", "content": "你好"}])]


@pytest.mark.asyncio
async def test_update_conversation_mirrors_new_history():
    db = FakeDB(_conversation())
    store = FakeLosslessStore()
    manager = ConversationManager(db, lossless_store=store)
    history = [
        {"role": "user", "content": "第一条"},
        {"role": "assistant", "content": "第二条"},
    ]

    await manager.update_conversation(
        unified_msg_origin="qq:group:1",
        conversation_id="conv-1",
        history=history,
    )

    assert db.updated_payloads[-1]["content"] == history
    assert store.calls == [("conv-1", history)]


@pytest.mark.asyncio
async def test_add_message_pair_updates_db_and_lossless_store():
    db = FakeDB(_conversation([{"role": "system", "content": "你是助手"}]))
    store = FakeLosslessStore()
    manager = ConversationManager(db, lossless_store=store)

    await manager.add_message_pair(
        "conv-1",
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "收到"},
    )

    assert len(db.conversation.content) == 3
    assert store.calls[-1][0] == "conv-1"
    assert store.calls[-1][1][-2:] == [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "收到"},
    ]


@pytest.mark.asyncio
async def test_lossless_store_failure_does_not_break_get_conversation():
    db = FakeDB(_conversation([{"role": "user", "content": "still works"}]))
    manager = ConversationManager(db, lossless_store=FakeLosslessStore(should_fail=True))

    conversation = await manager.get_conversation("qq:group:1", "conv-1")

    assert conversation is not None
    assert conversation.cid == "conv-1"
