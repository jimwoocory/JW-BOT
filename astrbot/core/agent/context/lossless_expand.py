"""Lossless expand / recall helpers — Phase 1D minimum viable recall.

Provides three recall primitives over the sidecar store:

* :meth:`LosslessExpander.expand_by_seq_range` — return raw messages in a seq window.
* :meth:`LosslessExpander.expand_summary_node` — return a summary node + coverage info.
* :meth:`LosslessExpander.grep_messages` — keyword search across raw messages.

No LLM calls are made here; all operations are pure SQLite queries.
Future Phase 1D work will expose these as agent tools via AstrBot's tool registry.
"""

from __future__ import annotations

import json
from typing import Any

from .lossless_store import LosslessContextStore

try:
    from astrbot import logger
except ImportError:
    import logging

    logger = logging.getLogger("astrbot")


class LosslessExpander:
    """Recall helpers for lossless context.

    Args:
        store: The sidecar :class:`LosslessContextStore` to query.
    """

    def __init__(self, store: LosslessContextStore) -> None:
        self.store = store

    async def expand_by_seq_range(
        self,
        conversation_id: str,
        start_seq: int,
        end_seq: int,
    ) -> list[dict[str, Any]]:
        """Return raw message dicts for ``[start_seq, end_seq]`` inclusive.

        Args:
            conversation_id: AstrBot conversation UUID.
            start_seq: First seq number (1-based).
            end_seq: Last seq number (inclusive).

        Returns:
            List of item dicts ordered by seq ascending.  Each dict has the
            same shape as a ``lossless_items`` row.  ``content_json`` is left
            as a raw JSON string; callers parse as needed.
        """
        items = await self.store.get_items_by_seq_range(
            conversation_id,
            start_seq,
            end_seq,
        )
        logger.debug(
            "[LOSSLESS_EXPAND] expand_by_seq_range %s [%d, %d] → %d items",
            conversation_id,
            start_seq,
            end_seq,
            len(items),
        )
        return items

    async def expand_summary_node(
        self,
        conversation_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        """Return a summary node dict plus its covered seq range.

        Args:
            conversation_id: AstrBot conversation UUID.
            item_id: The ``item_id`` of a ``summary_leaf`` item.

        Returns:
            A dict with keys:
            - ``item``: the raw item dict from the store.
            - ``summary_text``: extracted summary string.
            - ``source_start_seq``, ``source_end_seq``: coverage boundaries.
            - ``covered_item_ids``: list of child item_ids from ``lossless_links``.

        Raises:
            LookupError: When no item with ``item_id`` exists for this conversation.
        """
        import aiosqlite as _aiosqlite

        await self.store.initialize()
        async with _aiosqlite.connect(self.store.db_path) as db:
            db.row_factory = _aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT item_id, conversation_id, seq, item_type, role,
                       content_json, token_estimate, source_start_seq,
                       source_end_seq, created_at, status
                FROM lossless_items
                WHERE item_id = ?
                """,
                (item_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            raise LookupError(
                f"item_id {item_id!r} not found in conversation {conversation_id!r}"
            )
        target = dict(row)

        payload = json.loads(target["content_json"])
        summary_text = payload.get("summary", "")

        # Gather children from lossless_links
        links = await self.store.get_links(conversation_id)
        covered_ids = [
            lnk["child_item_id"]
            for lnk in links
            if lnk["parent_item_id"] == item_id and lnk["link_type"] == "covers"
        ]

        result = {
            "item": target,
            "summary_text": summary_text,
            "source_start_seq": target.get("source_start_seq"),
            "source_end_seq": target.get("source_end_seq"),
            "covered_item_ids": covered_ids,
        }
        logger.debug(
            "[LOSSLESS_EXPAND] expand_summary_node %s item_id=%s covers %d children",
            conversation_id,
            item_id,
            len(covered_ids),
        )
        return result

    async def grep_messages(
        self,
        conversation_id: str,
        keyword: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Case-insensitive keyword search over raw-message ``content_json``.

        Only ``raw_message`` items are searched (not summary nodes).

        Args:
            conversation_id: AstrBot conversation UUID.
            keyword: Search term.  Matched case-insensitively against the
                JSON-serialised content field.
            limit: Maximum number of results to return.

        Returns:
            List of matching item dicts, ordered by seq ascending.
        """
        if not keyword:
            return []

        keyword_lower = keyword.lower()
        items = await self.store.list_items(conversation_id, limit=10_000)
        results: list[dict[str, Any]] = []

        for item in items:
            if item.get("item_type") != "raw_message":
                continue
            if keyword_lower in item.get("content_json", "").lower():
                results.append(item)
                if len(results) >= limit:
                    break

        logger.debug(
            "[LOSSLESS_EXPAND] grep_messages %s keyword=%r → %d matches",
            conversation_id,
            keyword,
            len(results),
        )
        return results
