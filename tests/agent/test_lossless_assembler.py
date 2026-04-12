import pytest

from astrbot.core.agent.context.lossless_assembler import LosslessAssembler
from astrbot.core.agent.context.lossless_store import LosslessContextStore
from astrbot.core.agent.message import Message

SYSTEM = [Message(role="system", content="你是助手")]
FRESH = [
    Message(role="user", content="最新问题"),
    Message(role="assistant", content="最新回答"),
]


@pytest.mark.asyncio
async def test_assemble_without_summary_root_returns_raw(tmp_path):
    """When no compaction has happened, assemble is a pass-through."""
    store = LosslessContextStore(tmp_path / "lossless_context.db")
    assembler = LosslessAssembler(store)

    result = await assembler.assemble("conv-a", SYSTEM, FRESH)

    assert result == SYSTEM + FRESH


@pytest.mark.asyncio
async def test_assemble_with_summary_root_returns_summary_plus_fresh_tail(tmp_path):
    """After compaction, assemble returns [system, summary pair, fresh tail]."""
    store = LosslessContextStore(tmp_path / "lossless_context.db")
    assembler = LosslessAssembler(store)

    # Simulate a compacted state:
    # 1. Ingest some raw messages
    raw = [
        {"role": "user", "content": "旧问题1"},
        {"role": "assistant", "content": "旧回答1"},
        {"role": "user", "content": "旧问题2"},
        {"role": "assistant", "content": "旧回答2"},
    ]
    await store.ingest_messages("conv-b", raw)

    # 2. Write a summary_leaf
    summary_text = "这是对话历史的摘要"
    item_id = await store.write_summary_leaf(
        "conv-b",
        summary_text,
        source_start_seq=1,
        source_end_seq=3,
        token_estimate=20,
    )

    # 3. Update head to reflect compaction
    await store.update_head_after_compact(
        "conv-b",
        last_compacted_seq=3,
        fresh_tail_start_seq=4,
        active_summary_root_id=item_id,
    )

    result = await assembler.assemble("conv-b", SYSTEM, FRESH)

    # Should be: [system, summary-user, summary-ack, fresh…]
    assert result[0].role == "system"
    assert "[Compact summary of earlier conversation]" in result[1].content
    assert summary_text in result[1].content
    assert result[2].role == "assistant"
    assert result[-2].content == "最新问题"
    assert result[-1].content == "最新回答"


@pytest.mark.asyncio
async def test_assemble_falls_back_when_store_raises(tmp_path):
    """If get_head raises, assemble returns system + fresh_tail unchanged."""
    from unittest.mock import AsyncMock

    store = LosslessContextStore(tmp_path / "lossless_context.db")
    store.get_head = AsyncMock(side_effect=RuntimeError("db error"))
    assembler = LosslessAssembler(store)

    result = await assembler.assemble("conv-c", SYSTEM, FRESH)

    assert result == SYSTEM + FRESH
