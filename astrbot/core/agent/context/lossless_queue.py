"""Per-conversation operation serialization queue.

Ensures that ingest and compact operations for the same conversation_id
are strictly serialized: a compact job cannot interleave with the ingest
write + update_head commit of a concurrent ingest.

The store already holds per-conversation asyncio.Locks internally, but those
locks are per-DB-write.  This queue provides a higher-level lock that spans an
entire ingest or compact *transaction* (multiple DB writes that must appear
atomic from the scheduler's perspective).

Usage::

    queue = LosslessOperationQueue()

    # ingest path
    head = await queue.run_ingest(conv_id, store, messages)

    # compact path
    result = await queue.run_compact(conv_id, my_compact_coroutine())
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from .lossless_store import LosslessContextStore, LosslessHead

T = TypeVar("T")

try:
    from astrbot import logger
except ImportError:
    import logging

    logger = logging.getLogger("astrbot")


class LosslessOperationQueue:
    """Serializes high-level ingest/compact operations per conversation_id.

    One :class:`LosslessOperationQueue` instance should be shared across all
    code paths that mutate the sidecar store for a given AstrBot process.
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_ingest(
        self,
        conversation_id: str,
        store: LosslessContextStore,
        messages: list[dict[str, Any]],
    ) -> LosslessHead:
        """Run an ingest operation under the per-conversation high-level lock.

        Args:
            conversation_id: AstrBot conversation UUID.
            store: The sidecar store to write to.
            messages: Full current message list from AstrBot (idempotent).

        Returns:
            The updated :class:`LosslessHead` after ingest.
        """
        async with self._lock(conversation_id):
            return await store.ingest_messages(conversation_id, messages)

    async def run_compact(
        self,
        conversation_id: str,
        compact_coro: Coroutine[Any, Any, T],
    ) -> T:
        """Run a compaction coroutine under the per-conversation high-level lock.

        The caller builds a coroutine (e.g. ``compressor._write_to_sidecar(…)``)
        and hands it here.  The queue serializes it with any concurrent ingest.

        Args:
            conversation_id: AstrBot conversation UUID.
            compact_coro: Coroutine that performs the compaction DB writes.

        Returns:
            Whatever ``compact_coro`` returns.
        """
        async with self._lock(conversation_id):
            return await compact_coro

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _lock(self, conversation_id: str) -> asyncio.Lock:
        if conversation_id not in self._locks:
            self._locks[conversation_id] = asyncio.Lock()
        return self._locks[conversation_id]
