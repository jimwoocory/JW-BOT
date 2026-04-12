"""Lossless context assembler.

Rebuilds the model-facing message list from the sidecar DAG state:

    [system messages]
    + [summary_leaf pair]   ← only when active_summary_root_id is set
    + [fresh tail]          ← raw messages with seq > fresh_tail_start_seq

When no compaction has happened yet (``active_summary_root_id`` is None) the
assembler is a no-op and returns the original messages unchanged.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..message import Message

if TYPE_CHECKING:
    from .lossless_store import LosslessContextStore

try:
    from astrbot import logger
except ImportError:
    import logging

    logger = logging.getLogger("astrbot")

# Prefix injected before the summary text in the user turn.
_SUMMARY_USER_PREFIX = "[Compact summary of earlier conversation]\n"
# Acknowledgement text placed in the following assistant turn.
_SUMMARY_ASSISTANT_ACK = (
    "Acknowledged. I will use this compact summary together with the recent raw conversation."
)


class LosslessAssembler:
    """Assembles the LLM context from a sidecar DAG state.

    Usage::

        assembler = LosslessAssembler(store)
        messages = await assembler.assemble(
            conversation_id,
            system_messages,
            fresh_tail_messages,
        )
    """

    def __init__(self, store: LosslessContextStore) -> None:
        self.store = store

    async def assemble(
        self,
        conversation_id: str,
        system_messages: list[Message],
        fresh_tail_messages: list[Message],
    ) -> list[Message]:
        """Return the assembled context for an LLM call.

        If ``active_summary_root_id`` is None (no compaction recorded yet)
        the method returns ``system_messages + fresh_tail_messages`` unchanged —
        identical behaviour to the pre-lossless baseline.

        Args:
            conversation_id: AstrBot conversation UUID.
            system_messages: System-role messages (always kept first).
            fresh_tail_messages: Most-recent raw messages (always kept last).

        Returns:
            Assembled message list ready for the LLM call.
        """
        try:
            head = await self.store.get_head(conversation_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[LOSSLESS_ASSEMBLER] get_head failed for %s, returning raw: %s",
                conversation_id,
                exc,
            )
            return system_messages + fresh_tail_messages

        if not head.active_summary_root_id:
            # No compaction yet — pass through unchanged.
            return system_messages + fresh_tail_messages

        try:
            summary_text = await self._fetch_summary_text(
                conversation_id,
                head.active_summary_root_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[LOSSLESS_ASSEMBLER] fetch summary failed for %s (item_id=%s), returning raw: %s",
                conversation_id,
                head.active_summary_root_id,
                exc,
            )
            return system_messages + fresh_tail_messages

        summary_pair: list[Message] = [
            Message(
                role="user",
                content=f"{_SUMMARY_USER_PREFIX}{summary_text}",
            ),
            Message(
                role="assistant",
                content=_SUMMARY_ASSISTANT_ACK,
            ),
        ]

        logger.debug(
            "[LOSSLESS_ASSEMBLER] assembled context for %s: "
            "%d system + summary_pair + %d fresh_tail",
            conversation_id,
            len(system_messages),
            len(fresh_tail_messages),
        )

        return system_messages + summary_pair + fresh_tail_messages

    async def _fetch_summary_text(
        self,
        conversation_id: str,
        item_id: str,
    ) -> str:
        """Retrieve summary text from the sidecar store by item_id."""
        import aiosqlite

        await self.store.initialize()
        async with aiosqlite.connect(self.store.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT content_json FROM lossless_items WHERE item_id = ?",
                (item_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            raise LookupError(
                f"summary item {item_id!r} not found for conversation {conversation_id!r}"
            )
        payload = json.loads(row["content_json"])
        return payload.get("summary", "")
