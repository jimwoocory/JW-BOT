"""Lossless summary compressor — Phase 1C/1D.

Upgrades the previous conservative summarizer to a true leaf compaction:

1. Splits message history into ``[system | to_summarize | fresh_tail]``.
2. Sends ``to_summarize`` to the LLM for a compact summary.
3. Writes the summary as a ``summary_leaf`` item to the sidecar store.
4. Writes ``covers`` lineage links for each source item.
5. Updates the per-conversation ``lossless_heads`` checkpoint.
6. Returns the assembled context via :class:`LosslessAssembler` (or an
   inline fallback when the assembler is not wired).

If the sidecar write fails, the in-memory summary pair is still returned so
the LLM call proceeds — sidecar failure never blocks replies.

If the LLM summarization fails, the fallback compressor (turn truncation) is
used instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..message import Message
from .compressor import TruncateByTurnsCompressor, split_history

if TYPE_CHECKING:
    from astrbot.core.provider.provider import Provider

    from .lossless_assembler import LosslessAssembler
    from .lossless_store import LosslessContextStore

try:
    from astrbot import logger
except ImportError:
    import logging

    logger = logging.getLogger("astrbot")

# User turn prefix used for the in-memory summary pair (fallback path).
_SUMMARY_USER_PREFIX = "[Compact summary of earlier conversation]\n"
_SUMMARY_ASSISTANT_ACK = (
    "Acknowledged. I will use this compact summary together with the recent raw conversation."
)


class LosslessSummaryCompressor:
    """Phase 1C/1D lossless compressor with true leaf compaction.

    Parameters
    ----------
    provider:
        LLM provider used for summarization.  If ``None``, falls back to
        turn truncation immediately.
    keep_recent:
        Number of most-recent turns to protect as the fresh tail.
    instruction_text:
        Custom summarization prompt.  Defaults to a conservative CJK-friendly
        instruction.
    compression_threshold:
        Fraction of ``max_tokens`` that triggers compression (default 0.82).
    fallback_compressor:
        Used when the provider is unavailable or raises.
    store:
        Sidecar :class:`LosslessContextStore`.  When provided, a successful
        summary is persisted as a ``summary_leaf`` with lineage links.
    conversation_id:
        AstrBot conversation UUID.  Required when ``store`` is set.
    assembler:
        :class:`LosslessAssembler` instance.  When provided, the assembled
        context is built via the assembler rather than inline.
    """

    def __init__(
        self,
        provider: Provider | None = None,
        keep_recent: int = 6,
        instruction_text: str | None = None,
        compression_threshold: float = 0.82,
        message_threshold: int = 200,
        fallback_compressor: TruncateByTurnsCompressor | None = None,
        *,
        store: LosslessContextStore | None = None,
        conversation_id: str | None = None,
        assembler: LosslessAssembler | None = None,
    ) -> None:
        self.provider = provider
        self.keep_recent = keep_recent
        self.compression_threshold = compression_threshold
        self.message_threshold = message_threshold
        self.fallback_compressor = fallback_compressor or TruncateByTurnsCompressor()
        self.instruction_text = instruction_text or (
            "Summarize the older conversation history into a compact, durable note.\n"
            "1. Keep the user's original goal and current progress.\n"
            "2. Preserve decisions, constraints, pending tasks, and important tool results.\n"
            "3. Write in the user's language.\n"
            "4. Avoid inventing details not present in the history.\n"
        )
        self.store = store
        self.conversation_id = conversation_id
        self.assembler = assembler

    # ------------------------------------------------------------------
    # ContextCompressor protocol
    # ------------------------------------------------------------------

    def should_compress(
        self,
        messages: list[Message],
        current_tokens: int,
        max_tokens: int,
    ) -> bool:
        if len(messages) <= self.keep_recent + 1:
            return False
        non_system_messages = sum(1 for message in messages if message.role != "system")
        if self.message_threshold > 0 and non_system_messages >= self.message_threshold:
            return True
        if max_tokens <= 0 or current_tokens <= 0:
            return False
        usage_rate = current_tokens / max_tokens
        return usage_rate > self.compression_threshold

    async def __call__(self, messages: list[Message]) -> list[Message]:
        if len(messages) <= self.keep_recent + 1:
            return messages

        system_messages, messages_to_summarize, recent_messages = split_history(
            messages,
            self.keep_recent,
        )

        if not messages_to_summarize:
            return messages

        if self.provider is None:
            logger.warning(
                "[LOSSLESS] no provider configured, falling back to truncation",
            )
            return await self.fallback_compressor(messages)

        try:
            instruction_message = Message(role="user", content=self.instruction_text)
            llm_payload = messages_to_summarize + [instruction_message]
            response = await self.provider.text_chat(contexts=llm_payload)
            summary_content = response.completion_text.strip()
            if not summary_content:
                logger.warning(
                    "[LOSSLESS] LLM returned empty summary, falling back to truncation",
                )
                return await self.fallback_compressor(messages)
        except Exception as exc:
            logger.warning(
                "[LOSSLESS] LLM summarization failed, falling back to truncation: %s",
                exc,
            )
            return await self.fallback_compressor(messages)

        # ---- sidecar write (best-effort) --------------------------------
        token_estimate = sum(
            len(m.content) if isinstance(m.content, str) else 0
            for m in messages_to_summarize
        )
        await self._try_persist_summary(
            summary_content=summary_content,
            messages_to_summarize=messages_to_summarize,
            recent_messages=recent_messages,
            source_token_estimate=token_estimate,
        )

        # ---- assemble context -------------------------------------------
        if self.assembler and self.conversation_id:
            try:
                return await self.assembler.assemble(
                    self.conversation_id,
                    system_messages,
                    recent_messages,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "[LOSSLESS] assembler failed, using inline assembly: %s",
                    exc,
                )

        # Inline fallback assembly (assembler not wired or failed)
        return [
            *system_messages,
            Message(
                role="user",
                content=f"{_SUMMARY_USER_PREFIX}{summary_content}",
            ),
            Message(
                role="assistant",
                content=_SUMMARY_ASSISTANT_ACK,
            ),
            *recent_messages,
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _try_persist_summary(
        self,
        *,
        summary_content: str,
        messages_to_summarize: list[Message],
        recent_messages: list[Message],
        source_token_estimate: int,
    ) -> None:
        """Persist summary_leaf + lineage to the sidecar store.

        All errors are caught and logged — a sidecar write failure must never
        block the LLM call.
        """
        if not self.store or not self.conversation_id:
            return

        try:
            head = await self.store.get_head(self.conversation_id)

            # --- Bug-1 fix: validate that in-memory summarized count matches sidecar ---
            #
            # The in-memory compressor works on messages that may have been
            # pre-truncated (by enforce_max_turns) BEFORE the compressor was
            # called.  The sidecar, however, has the full untruncated history.
            # If the two counts diverge, the seq range we'd compute from the
            # sidecar head would be wrong — covering messages that were never
            # part of the actual LLM summary call.
            #
            # Resolution: require the counts to agree before writing.  The
            # in-memory summary is always returned to the caller regardless;
            # only the sidecar persistence is skipped on mismatch.
            #
            # sidecar_available = messages since last compaction (all of them)
            sidecar_available: int = head.last_ingested_seq - head.last_compacted_seq

            # in-memory tells us exactly how many messages went into the summary
            in_memory_summarized: int = len(messages_to_summarize)

            # The fresh tail kept by the compressor.
            fresh_tail_count: int = len(recent_messages)

            # What the sidecar thinks should be in the summary:
            sidecar_expected_in_summary: int = sidecar_available - fresh_tail_count

            if sidecar_expected_in_summary != in_memory_summarized:
                logger.warning(
                    "[LOSSLESS] summary coverage mismatch for %s: "
                    "in-memory summarized %d messages, "
                    "but sidecar expected %d (last_ingested=%d, last_compacted=%d, "
                    "fresh_tail=%d). "
                    "Pre-truncation or ingest lag detected — skipping sidecar write.",
                    self.conversation_id,
                    in_memory_summarized,
                    sidecar_expected_in_summary,
                    head.last_ingested_seq,
                    head.last_compacted_seq,
                    fresh_tail_count,
                )
                return

            # Counts agree: compute the seq range from the sidecar head.
            source_start_seq = head.last_compacted_seq + 1
            source_end_seq = head.last_ingested_seq - fresh_tail_count

            if source_end_seq < source_start_seq:
                # Nothing new to compact (e.g. ingest hasn't caught up yet).
                logger.debug(
                    "[LOSSLESS] nothing to compact for %s "
                    "(source_start=%d, source_end=%d)",
                    self.conversation_id,
                    source_start_seq,
                    source_end_seq,
                )
                return

            summary_token_estimate = len(summary_content) // 2  # rough CJK estimate

            async with self.store._conversation_lock(self.conversation_id):  # noqa: SLF001
                summary_item_id = await self.store.write_summary_leaf(
                    self.conversation_id,
                    summary_content,
                    source_start_seq,
                    source_end_seq,
                    summary_token_estimate,
                )

                # Write "covers" links for every source item in the range.
                source_items = await self.store.get_items_by_seq_range(
                    self.conversation_id,
                    source_start_seq,
                    source_end_seq,
                )
                for item in source_items:
                    await self.store.write_lossless_link(
                        summary_item_id,
                        item["item_id"],
                        "covers",
                    )

                new_fresh_tail_start = source_end_seq + 1
                await self.store.update_head_after_compact(
                    self.conversation_id,
                    last_compacted_seq=source_end_seq,
                    fresh_tail_start_seq=new_fresh_tail_start,
                    active_summary_root_id=summary_item_id,
                )

            logger.info(
                "[LOSSLESS] summary_leaf written: item_id=%s, "
                "covers seqs %d-%d, summary_tokens=%d, source_tokens=%d",
                summary_item_id,
                source_start_seq,
                source_end_seq,
                summary_token_estimate,
                source_token_estimate,
            )

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[LOSSLESS] sidecar write failed, in-memory summary still used: %s",
                exc,
            )
