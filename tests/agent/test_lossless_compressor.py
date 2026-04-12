from unittest.mock import AsyncMock

import pytest

from astrbot.core.agent.context.lossless_compressor import LosslessSummaryCompressor
from astrbot.core.agent.context.lossless_store import LosslessContextStore
from astrbot.core.agent.message import Message
from astrbot.core.provider.entities import LLMResponse


class MockProvider:
    async def text_chat(self, **kwargs):
        messages = kwargs.get("contexts", [])
        return LLMResponse(
            role="assistant",
            completion_text=f"历史摘要，共 {len(messages) - 1} 条旧消息。",
        )


def _messages() -> list[Message]:
    return [
        Message(role="system", content="你是助手"),
        Message(role="user", content="需求 1"),
        Message(role="assistant", content="回复 1"),
        Message(role="user", content="需求 2"),
        Message(role="assistant", content="回复 2"),
        Message(role="user", content="需求 3"),
        Message(role="assistant", content="回复 3"),
        Message(role="user", content="最新需求"),
        Message(role="assistant", content="最新回复"),
    ]


class TestLosslessSummaryCompressor:
    def test_should_compress_above_threshold(self):
        compressor = LosslessSummaryCompressor(keep_recent=4)
        assert compressor.should_compress(_messages(), current_tokens=90, max_tokens=100)

    def test_should_not_compress_when_too_short(self):
        compressor = LosslessSummaryCompressor(keep_recent=10)
        assert not compressor.should_compress(_messages(), current_tokens=90, max_tokens=100)

    def test_should_compress_when_message_threshold_hit(self):
        compressor = LosslessSummaryCompressor(
            keep_recent=4,
            message_threshold=8,
        )
        assert compressor.should_compress(_messages(), current_tokens=10, max_tokens=1_000_000)

    @pytest.mark.asyncio
    async def test_preserves_fresh_tail_and_system_messages(self):
        compressor = LosslessSummaryCompressor(
            provider=MockProvider(),  # type: ignore[arg-type]
            keep_recent=4,
        )

        result = await compressor(_messages())

        assert result[0].role == "system"
        assert "[Compact summary of earlier conversation]" in str(result[1].content)
        assert result[-2].content == "最新需求"
        assert result[-1].content == "最新回复"

    @pytest.mark.asyncio
    async def test_falls_back_when_provider_fails(self):
        provider = MockProvider()
        provider.text_chat = AsyncMock(side_effect=RuntimeError("boom"))
        compressor = LosslessSummaryCompressor(
            provider=provider,  # type: ignore[arg-type]
            keep_recent=4,
        )

        result = await compressor(_messages())

        assert len(result) < len(_messages())
        assert all("[Compact summary of earlier conversation]" not in str(msg.content) for msg in result)

    @pytest.mark.asyncio
    async def test_falls_back_without_provider(self):
        compressor = LosslessSummaryCompressor(keep_recent=4)

        result = await compressor(_messages())

        assert len(result) < len(_messages())

    @pytest.mark.asyncio
    async def test_compressor_writes_summary_leaf_on_success(self, tmp_path):
        store = LosslessContextStore(tmp_path / "lossless_context.db")
        # Pre-ingest so head exists
        raw = [{"role": m.role, "content": m.content} for m in _messages() if m.role != "system"]
        await store.ingest_messages("conv-x", raw)

        compressor = LosslessSummaryCompressor(
            provider=MockProvider(),  # type: ignore[arg-type]
            keep_recent=4,
            store=store,
            conversation_id="conv-x",
        )

        result = await compressor(_messages())

        # Summary leaf should now exist in the sidecar
        head = await store.get_head("conv-x")
        assert head.active_summary_root_id is not None
        items = await store.list_items("conv-x", limit=100)
        summary_items = [i for i in items if i["item_type"] == "summary_leaf"]
        assert len(summary_items) >= 1

        # Fresh tail still present in result
        assert result[-2].content == "最新需求"
        assert result[-1].content == "最新回复"

    @pytest.mark.asyncio
    async def test_fresh_tail_never_lost(self, tmp_path):
        """Even when compaction writes to sidecar, keep_recent messages are always in result."""
        store = LosslessContextStore(tmp_path / "lossless_context.db")
        raw = [{"role": m.role, "content": m.content} for m in _messages() if m.role != "system"]
        await store.ingest_messages("conv-y", raw)

        compressor = LosslessSummaryCompressor(
            provider=MockProvider(),  # type: ignore[arg-type]
            keep_recent=4,
            store=store,
            conversation_id="conv-y",
        )

        result = await compressor(_messages())
        contents = [str(m.content) for m in result]
        assert "最新需求" in contents
        assert "最新回复" in contents

    @pytest.mark.asyncio
    async def test_compressor_falls_back_on_provider_failure_and_does_not_corrupt_store(
        self, tmp_path
    ):
        store = LosslessContextStore(tmp_path / "lossless_context.db")
        raw = [{"role": m.role, "content": m.content} for m in _messages() if m.role != "system"]
        await store.ingest_messages("conv-z", raw)
        head_before = await store.get_head("conv-z")

        provider = MockProvider()
        provider.text_chat = AsyncMock(side_effect=RuntimeError("boom"))
        compressor = LosslessSummaryCompressor(
            provider=provider,  # type: ignore[arg-type]
            keep_recent=4,
            store=store,
            conversation_id="conv-z",
        )

        result = await compressor(_messages())

        # Fallback truncation was used — no summary leaf written
        head_after = await store.get_head("conv-z")
        assert head_after.active_summary_root_id == head_before.active_summary_root_id
        assert len(result) < len(_messages())

    @pytest.mark.asyncio
    async def test_summary_leaf_covers_correct_source_seqs(self, tmp_path):
        store = LosslessContextStore(tmp_path / "lossless_context.db")
        raw = [{"role": m.role, "content": m.content} for m in _messages() if m.role != "system"]
        await store.ingest_messages("conv-w", raw)

        compressor = LosslessSummaryCompressor(
            provider=MockProvider(),  # type: ignore[arg-type]
            keep_recent=4,
            store=store,
            conversation_id="conv-w",
        )

        await compressor(_messages())

        items = await store.list_items("conv-w", limit=100)
        leaf = next((i for i in items if i["item_type"] == "summary_leaf"), None)
        assert leaf is not None
        assert leaf["source_start_seq"] >= 1
        assert leaf["source_end_seq"] >= leaf["source_start_seq"]

        # Lineage links exist
        links = await store.get_links("conv-w")
        covers_links = [lnk for lnk in links if lnk["link_type"] == "covers"]
        assert len(covers_links) >= 1

    # ------------------------------------------------------------------
    # Bug-regression tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_bug1_coverage_mismatch_skips_sidecar_write(self, tmp_path):
        """Bug 1: if the in-memory summarized count doesn't match the sidecar
        expected count (e.g. because max-turns pre-truncation dropped messages),
        the compressor must NOT write a summary_leaf with a wrong seq range.
        The in-memory summary is still returned — only sidecar persistence is skipped.
        """
        store = LosslessContextStore(tmp_path / "lossless_context.db")

        # Sidecar has 8 raw messages ingested.
        full_history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
                        for i in range(8)]
        await store.ingest_messages("conv-bug1", full_history)
        head_before = await store.get_head("conv-bug1")
        assert head_before.last_ingested_seq == 8

        # But the compressor only receives 5 messages (3 were dropped by pre-truncation).
        # This simulates what happens when enforce_max_turns fires before the compressor.
        truncated_messages = [
            Message(role="system", content="sys"),
            Message(role="user", content="msg3"),
            Message(role="assistant", content="msg4"),
            Message(role="user", content="msg5"),   # fresh tail starts here
            Message(role="assistant", content="msg6"),
        ]

        compressor = LosslessSummaryCompressor(
            provider=MockProvider(),  # type: ignore[arg-type]
            keep_recent=2,
            store=store,
            conversation_id="conv-bug1",
        )
        # keep_recent=2 → messages_to_summarize has 1 pair = 2 msgs; sidecar expects 8-2=6 → mismatch
        result = await compressor(truncated_messages)

        # In-memory result is still returned (summary or fallback).
        assert result is not None

        # Sidecar must NOT have been mutated — no summary_leaf written.
        head_after = await store.get_head("conv-bug1")
        assert head_after.active_summary_root_id is None
        items = await store.list_items("conv-bug1", limit=200)
        summary_items = [i for i in items if i["item_type"] == "summary_leaf"]
        assert len(summary_items) == 0

    @pytest.mark.asyncio
    async def test_bug2_no_seq_collision_for_different_start_same_end(self, tmp_path):
        """Bug 2: two summary_leaf items that share the same source_end_seq but
        have different source_start_seq must NOT collide on the SQLite UNIQUE
        (conversation_id, seq) constraint.  Both writes must succeed and produce
        distinct rows.
        """
        store = LosslessContextStore(tmp_path / "lossless_context.db")

        # Write two summary_leaf items: same end, different start.
        item_a = await store.write_summary_leaf(
            "conv-bug2", "summary A", source_start_seq=1, source_end_seq=5, token_estimate=10
        )
        item_b = await store.write_summary_leaf(
            "conv-bug2", "summary B", source_start_seq=3, source_end_seq=5, token_estimate=10
        )

        assert item_a != item_b  # different item_ids

        # Both must exist in the DB.
        items = await store.list_items("conv-bug2", limit=200)
        summary_seqs = [(i["item_id"], i["source_start_seq"], i["source_end_seq"])
                        for i in items if i["item_type"] == "summary_leaf"]
        ids_written = {t[0] for t in summary_seqs}
        assert item_a in ids_written, "summary A was silently ignored — seq collision!"
        assert item_b in ids_written, "summary B was silently ignored — seq collision!"
