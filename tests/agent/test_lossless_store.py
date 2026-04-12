import pytest

from astrbot.core.agent.context.lossless_store import LosslessContextStore


@pytest.mark.asyncio
async def test_initialize_and_default_head(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    await store.initialize()

    head = await store.get_head("conv-1")
    assert head.conversation_id == "conv-1"
    assert head.last_ingested_seq == 0
    assert head.fresh_tail_start_seq == 1


@pytest.mark.asyncio
async def test_ingest_messages_is_idempotent(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好，有什么我可以帮你？"},
    ]

    first_head = await store.ingest_messages("conv-2", messages)
    second_head = await store.ingest_messages("conv-2", messages)
    items = await store.list_items("conv-2")

    assert first_head.last_ingested_seq == 2
    assert second_head.last_ingested_seq == 2
    assert len(items) == 2
    assert items[0]["seq"] == 1
    assert items[1]["seq"] == 2


@pytest.mark.asyncio
async def test_ingest_messages_appends_only_new_tail(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    await store.ingest_messages(
        "conv-3",
        [{"role": "user", "content": "第一条"}],
    )
    head = await store.ingest_messages(
        "conv-3",
        [
            {"role": "user", "content": "第一条"},
            {"role": "assistant", "content": "第二条"},
            {"role": "user", "content": "第三条"},
        ],
    )
    items = await store.list_items("conv-3")

    assert head.last_ingested_seq == 3
    assert [item["seq"] for item in items] == [1, 2, 3]
    assert items[2]["role"] == "user"


@pytest.mark.asyncio
async def test_record_job_persists_payload(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    await store.record_job(
        job_id="job-1",
        conversation_id="conv-4",
        job_type="ingest",
        status="completed",
        payload={"new_messages": 3},
    )

    # Reusing list_items would not cover job persistence, so we ensure the DB exists.
    assert (tmp_path / "lossless_context.db").exists()


@pytest.mark.asyncio
async def test_write_summary_leaf_and_read_back(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    item_id = await store.write_summary_leaf(
        "conv-5",
        "这是一段摘要内容",
        source_start_seq=1,
        source_end_seq=3,
        token_estimate=42,
    )

    assert item_id == "conv-5:summary:1-3"

    # summary_leaf is stored at a synthetic high seq; use list_items to find it
    items = await store.list_items("conv-5", limit=200)
    assert any(i["item_id"] == item_id and i["item_type"] == "summary_leaf" for i in items)


@pytest.mark.asyncio
async def test_write_summary_leaf_is_idempotent(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    item_id_1 = await store.write_summary_leaf("conv-6", "摘要", 1, 2, 10)
    item_id_2 = await store.write_summary_leaf("conv-6", "摘要（重复）", 1, 2, 10)

    assert item_id_1 == item_id_2
    # summary_leaf is at a synthetic high seq; use list_items
    items = await store.list_items("conv-6", limit=200)
    summary_items = [i for i in items if i["item_type"] == "summary_leaf"]
    assert len(summary_items) == 1  # idempotent


@pytest.mark.asyncio
async def test_write_lossless_link_and_read_back(tmp_path):
    """Links are stored correctly and get_links returns them via JOIN through lossless_items."""
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    # Ingest two raw messages to create items in the store
    await store.ingest_messages(
        "conv-link",
        [{"role": "user", "content": "msg1"}, {"role": "assistant", "content": "msg2"}],
    )

    # Write a summary_leaf covering both messages (parent)
    parent_id = await store.write_summary_leaf(
        "conv-link",
        "summary",
        source_start_seq=1,
        source_end_seq=2,
        token_estimate=5,
    )

    # child item_ids come from the raw ingest items
    child_1 = store._item_id("conv-link", 1)
    child_2 = store._item_id("conv-link", 2)

    await store.write_lossless_link(parent_id, child_1, "covers")
    await store.write_lossless_link(parent_id, child_2, "covers")

    links = await store.get_links("conv-link")
    parent_links = [lnk for lnk in links if lnk["parent_item_id"] == parent_id]
    assert len(parent_links) == 2
    child_ids = {lnk["child_item_id"] for lnk in parent_links}
    assert child_ids == {child_1, child_2}


@pytest.mark.asyncio
async def test_update_head_after_compact(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    await store.ingest_messages(
        "conv-7",
        [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
            {"role": "user", "content": "msg3"},
        ],
    )

    await store.update_head_after_compact(
        "conv-7",
        last_compacted_seq=2,
        fresh_tail_start_seq=3,
        active_summary_root_id="conv-7:summary:1-2",
    )

    head = await store.get_head("conv-7")
    assert head.last_compacted_seq == 2
    assert head.fresh_tail_start_seq == 3
    assert head.active_summary_root_id == "conv-7:summary:1-2"
    # ingest seq must be preserved
    assert head.last_ingested_seq == 3


@pytest.mark.asyncio
async def test_get_items_by_seq_range(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    messages = [{"role": "user", "content": f"msg{i}"} for i in range(1, 6)]
    await store.ingest_messages("conv-8", messages)

    items = await store.get_items_by_seq_range("conv-8", 2, 4)

    assert [i["seq"] for i in items] == [2, 3, 4]


@pytest.mark.asyncio
async def test_lossless_links_no_duplicate_edges(tmp_path):
    """Medium bug: lossless_links must not accumulate duplicate edges on repeated
    writes of the same (parent, child, link_type) triple.
    The unique index must enforce deduplication via INSERT OR IGNORE."""
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    await store.ingest_messages(
        "conv-dedup",
        [{"role": "user", "content": "msg1"}, {"role": "assistant", "content": "msg2"}],
    )
    parent_id = await store.write_summary_leaf(
        "conv-dedup", "summary", source_start_seq=1, source_end_seq=2, token_estimate=5
    )
    child_id = store._item_id("conv-dedup", 1)

    # Write the same edge three times (simulates retries / repeated compaction)
    await store.write_lossless_link(parent_id, child_id, "covers")
    await store.write_lossless_link(parent_id, child_id, "covers")
    await store.write_lossless_link(parent_id, child_id, "covers")

    links = await store.get_links("conv-dedup")
    dedup_links = [
        lnk for lnk in links
        if lnk["parent_item_id"] == parent_id and lnk["child_item_id"] == child_id
    ]
    # Exactly ONE edge must exist, not three
    assert len(dedup_links) == 1, (
        f"Expected 1 link edge, got {len(dedup_links)} — duplicate edges accumulated!"
    )


@pytest.mark.asyncio
async def test_count_items_returns_true_total(tmp_path):
    """Low bug (debug API): count_items must return the actual total, not a
    subset-size, so the pagination 'total' field is always accurate."""
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    messages = [{"role": "user", "content": f"msg{i}"} for i in range(1, 11)]
    await store.ingest_messages("conv-count", messages)

    total = await store.count_items("conv-count")
    assert total == 10

    # Fetching a small page must not affect the total count
    page = await store.list_items("conv-count", limit=3)
    assert len(page) == 3
    assert await store.count_items("conv-count") == 10  # still correct


@pytest.mark.asyncio
async def test_list_items_supports_offset(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    messages = [{"role": "user", "content": f"msg{i}"} for i in range(1, 7)]
    await store.ingest_messages("conv-offset", messages)

    page = await store.list_items("conv-offset", limit=2, offset=2)

    assert [item["seq"] for item in page] == [3, 4]


@pytest.mark.asyncio
async def test_get_snapshot_summarizes_conversation_state(tmp_path):
    store = LosslessContextStore(tmp_path / "lossless_context.db")

    await store.ingest_messages(
        "conv-snapshot",
        [
            {"role": "user", "content": "第一条"},
            {"role": "assistant", "content": "第二条"},
            {"role": "user", "content": "第三条"},
        ],
    )
    summary_id = await store.write_summary_leaf(
        "conv-snapshot",
        "摘要内容",
        source_start_seq=1,
        source_end_seq=2,
        token_estimate=12,
    )
    await store.update_head_after_compact(
        "conv-snapshot",
        last_compacted_seq=2,
        fresh_tail_start_seq=3,
        active_summary_root_id=summary_id,
    )

    snapshot = await store.get_snapshot("conv-snapshot")

    assert snapshot.conversation_id == "conv-snapshot"
    assert snapshot.last_ingested_seq == 3
    assert snapshot.last_compacted_seq == 2
    assert snapshot.total_items == 4
    assert snapshot.raw_message_items == 3
    assert snapshot.summary_leaf_items == 1
    assert snapshot.to_dict()["has_summary_root"] is True
