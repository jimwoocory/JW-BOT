import pytest

from astrbot.core.agent.context.lossless_expand import LosslessExpander
from astrbot.core.agent.context.lossless_store import LosslessContextStore


async def _seeded_store(tmp_path):
    """Return a store seeded with 5 raw messages + 1 summary_leaf."""
    store = LosslessContextStore(tmp_path / "lossless_context.db")
    messages = [
        {"role": "user", "content": "消息一"},
        {"role": "assistant", "content": "回复一"},
        {"role": "user", "content": "消息二"},
        {"role": "assistant", "content": "回复二"},
        {"role": "user", "content": "最新消息"},
    ]
    await store.ingest_messages("conv-e", messages)

    # Write a summary_leaf covering seqs 1-3
    item_id = await store.write_summary_leaf(
        "conv-e",
        "前三条消息的摘要",
        source_start_seq=1,
        source_end_seq=3,
        token_estimate=15,
    )
    # Write lineage
    source_items = await store.get_items_by_seq_range("conv-e", 1, 3)
    for item in source_items:
        await store.write_lossless_link(item_id, item["item_id"], "covers")

    return store, item_id


@pytest.mark.asyncio
async def test_expand_by_seq_range(tmp_path):
    store, _ = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    items = await expander.expand_by_seq_range("conv-e", 2, 4)

    seqs = [i["seq"] for i in items]
    assert seqs == [2, 3, 4]


@pytest.mark.asyncio
async def test_expand_by_seq_range_empty_when_no_match(tmp_path):
    store, _ = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    items = await expander.expand_by_seq_range("conv-e", 99, 100)

    assert items == []


@pytest.mark.asyncio
async def test_expand_summary_node(tmp_path):
    store, item_id = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    result = await expander.expand_summary_node("conv-e", item_id)

    assert result["summary_text"] == "前三条消息的摘要"
    assert result["source_start_seq"] == 1
    assert result["source_end_seq"] == 3
    assert len(result["covered_item_ids"]) == 3


@pytest.mark.asyncio
async def test_expand_summary_node_raises_on_unknown_id(tmp_path):
    store, _ = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    with pytest.raises(LookupError):
        await expander.expand_summary_node("conv-e", "does-not-exist")


@pytest.mark.asyncio
async def test_grep_messages_case_insensitive(tmp_path):
    store, _ = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    results = await expander.grep_messages("conv-e", "消息")

    # "消息一", "消息二", "最新消息" should all match
    assert len(results) == 3
    assert all(r["item_type"] == "raw_message" for r in results)


@pytest.mark.asyncio
async def test_grep_messages_limit(tmp_path):
    store, _ = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    results = await expander.grep_messages("conv-e", "消息", limit=2)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_grep_messages_no_match(tmp_path):
    store, _ = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    results = await expander.grep_messages("conv-e", "完全不存在的词")

    assert results == []


@pytest.mark.asyncio
async def test_grep_empty_keyword_returns_empty(tmp_path):
    store, _ = await _seeded_store(tmp_path)
    expander = LosslessExpander(store)

    results = await expander.grep_messages("conv-e", "")

    assert results == []
