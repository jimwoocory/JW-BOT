import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from .token_counter import EstimateTokenCounter


@dataclass(slots=True)
class LosslessHead:
    conversation_id: str
    last_ingested_seq: int = 0
    fresh_tail_start_seq: int = 1
    last_compacted_seq: int = 0
    active_summary_root_id: str | None = None


@dataclass(slots=True)
class LosslessConversationSnapshot:
    conversation_id: str
    last_ingested_seq: int
    fresh_tail_start_seq: int
    last_compacted_seq: int
    active_summary_root_id: str | None
    total_items: int
    raw_message_items: int
    summary_leaf_items: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "last_ingested_seq": self.last_ingested_seq,
            "fresh_tail_start_seq": self.fresh_tail_start_seq,
            "last_compacted_seq": self.last_compacted_seq,
            "active_summary_root_id": self.active_summary_root_id,
            "total_items": self.total_items,
            "raw_message_items": self.raw_message_items,
            "summary_leaf_items": self.summary_leaf_items,
            "has_summary_root": self.active_summary_root_id is not None,
        }


class LosslessContextStore:
    """Sidecar store for future lossless context compaction work.

    Phase 1B keeps this store observational only:

    - mirrors raw conversation messages
    - tracks per-conversation head state
    - records future ingest/compaction jobs
    - does not mutate AstrBot's primary conversation storage
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._initialized = False
        self._locks: dict[str, asyncio.Lock] = {}
        self._token_counter = EstimateTokenCounter()

    async def initialize(self) -> None:
        if self._initialized:
            return

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS lossless_items (
                    item_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    item_type TEXT NOT NULL,
                    role TEXT,
                    content_json TEXT NOT NULL,
                    token_estimate INTEGER NOT NULL DEFAULT 0,
                    source_start_seq INTEGER,
                    source_end_seq INTEGER,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    UNIQUE(conversation_id, seq)
                );

                CREATE TABLE IF NOT EXISTS lossless_links (
                    parent_item_id TEXT NOT NULL,
                    child_item_id TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS lossless_heads (
                    conversation_id TEXT PRIMARY KEY,
                    last_ingested_seq INTEGER NOT NULL DEFAULT 0,
                    fresh_tail_start_seq INTEGER NOT NULL DEFAULT 1,
                    last_compacted_seq INTEGER NOT NULL DEFAULT 0,
                    active_summary_root_id TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS lossless_jobs (
                    job_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error TEXT,
                    payload_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_lossless_items_conversation_seq
                ON lossless_items(conversation_id, seq);

                CREATE INDEX IF NOT EXISTS idx_lossless_jobs_conversation
                ON lossless_jobs(conversation_id, started_at);
            """)
            # Deduplicate existing edges before adding the unique index.
            # This keeps initialization safe for both fresh DBs and old DBs
            # that may already contain repeated lineage rows.
            await db.execute("""
                DELETE FROM lossless_links
                WHERE rowid NOT IN (
                    SELECT MIN(rowid)
                    FROM lossless_links
                    GROUP BY parent_item_id, child_item_id, link_type
                )
            """)
            await db.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_lossless_links_unique_edge
                ON lossless_links(parent_item_id, child_item_id, link_type)
            """)
            await db.commit()

        self._initialized = True

    async def ingest_messages(
        self,
        conversation_id: str,
        messages: list[dict[str, Any]],
    ) -> LosslessHead:
        await self.initialize()

        async with self._conversation_lock(conversation_id):
            head = await self.get_head(conversation_id)
            existing_count = head.last_ingested_seq

            if len(messages) <= existing_count:
                return head

            now = self._utcnow()
            new_messages = messages[existing_count:]

            async with aiosqlite.connect(self.db_path) as db:
                for offset, message in enumerate(new_messages, start=existing_count + 1):
                    payload = json.dumps(message, ensure_ascii=False, sort_keys=True)
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO lossless_items (
                            item_id,
                            conversation_id,
                            seq,
                            item_type,
                            role,
                            content_json,
                            token_estimate,
                            source_start_seq,
                            source_end_seq,
                            created_at,
                            status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            self._item_id(conversation_id, offset),
                            conversation_id,
                            offset,
                            "raw_message",
                            message.get("role"),
                            payload,
                            self._estimate_message_tokens(payload),
                            offset,
                            offset,
                            now,
                            "active",
                        ),
                    )

                await db.execute(
                    """
                    INSERT INTO lossless_heads (
                        conversation_id,
                        last_ingested_seq,
                        fresh_tail_start_seq,
                        last_compacted_seq,
                        active_summary_root_id,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(conversation_id) DO UPDATE SET
                        last_ingested_seq = excluded.last_ingested_seq,
                        updated_at = excluded.updated_at
                    """,
                    (
                        conversation_id,
                        len(messages),
                        1,
                        head.last_compacted_seq,
                        head.active_summary_root_id,
                        now,
                    ),
                )
                await db.commit()

            return LosslessHead(
                conversation_id=conversation_id,
                last_ingested_seq=len(messages),
                fresh_tail_start_seq=head.fresh_tail_start_seq,
                last_compacted_seq=head.last_compacted_seq,
                active_summary_root_id=head.active_summary_root_id,
            )

    async def get_head(self, conversation_id: str) -> LosslessHead:
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    conversation_id,
                    last_ingested_seq,
                    fresh_tail_start_seq,
                    last_compacted_seq,
                    active_summary_root_id
                FROM lossless_heads
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            return LosslessHead(conversation_id=conversation_id)

        return LosslessHead(
            conversation_id=row["conversation_id"],
            last_ingested_seq=row["last_ingested_seq"],
            fresh_tail_start_seq=row["fresh_tail_start_seq"],
            last_compacted_seq=row["last_compacted_seq"],
            active_summary_root_id=row["active_summary_root_id"],
        )

    async def list_items(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    item_id,
                    conversation_id,
                    seq,
                    item_type,
                    role,
                    content_json,
                    token_estimate,
                    source_start_seq,
                    source_end_seq,
                    created_at,
                    status
                FROM lossless_items
                WHERE conversation_id = ?
                ORDER BY seq ASC
                LIMIT ?
                OFFSET ?
                """,
                (conversation_id, limit, offset),
            )
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def count_items(self, conversation_id: str) -> int:
        """Return the total number of items stored for a conversation."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM lossless_items WHERE conversation_id = ?",
                (conversation_id,),
            )
            row = await cursor.fetchone()

        return row[0] if row else 0

    async def get_snapshot(
        self,
        conversation_id: str,
    ) -> LosslessConversationSnapshot:
        """Return a compact runtime snapshot for Harness/session consumers."""
        await self.initialize()

        head = await self.get_head(conversation_id)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    COUNT(*) AS total_items,
                    SUM(CASE WHEN item_type = 'raw_message' THEN 1 ELSE 0 END) AS raw_message_items,
                    SUM(CASE WHEN item_type = 'summary_leaf' THEN 1 ELSE 0 END) AS summary_leaf_items
                FROM lossless_items
                WHERE conversation_id = ?
                """,
                (conversation_id,),
            )
            row = await cursor.fetchone()

        total_items = row["total_items"] if row and row["total_items"] is not None else 0
        raw_message_items = (
            row["raw_message_items"]
            if row and row["raw_message_items"] is not None
            else 0
        )
        summary_leaf_items = (
            row["summary_leaf_items"]
            if row and row["summary_leaf_items"] is not None
            else 0
        )

        return LosslessConversationSnapshot(
            conversation_id=conversation_id,
            last_ingested_seq=head.last_ingested_seq,
            fresh_tail_start_seq=head.fresh_tail_start_seq,
            last_compacted_seq=head.last_compacted_seq,
            active_summary_root_id=head.active_summary_root_id,
            total_items=total_items,
            raw_message_items=raw_message_items,
            summary_leaf_items=summary_leaf_items,
        )

    async def record_job(
        self,
        *,
        job_id: str,
        conversation_id: str,
        job_type: str,
        status: str,
        started_at: str | None = None,
        finished_at: str | None = None,
        error: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO lossless_jobs (
                    job_id,
                    conversation_id,
                    job_type,
                    status,
                    started_at,
                    finished_at,
                    error,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    conversation_id,
                    job_type,
                    status,
                    started_at or self._utcnow(),
                    finished_at,
                    error,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True)
                    if payload is not None
                    else None,
                ),
            )
            await db.commit()

    async def write_summary_leaf(
        self,
        conversation_id: str,
        summary_content: str,
        source_start_seq: int,
        source_end_seq: int,
        token_estimate: int,
    ) -> str:
        """Insert a summary_leaf item and return its item_id.

        The item_id is deterministic: ``{conversation_id}:summary:{source_start_seq}-{source_end_seq}``.
        Uses INSERT OR IGNORE so repeated calls with the same range are idempotent.
        Caller is responsible for holding the per-conversation lock.
        """
        await self.initialize()

        item_id = f"{conversation_id}:summary:{source_start_seq}-{source_end_seq}"
        now = self._utcnow()
        payload = json.dumps(
            {"summary": summary_content},
            ensure_ascii=False,
        )

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO lossless_items (
                    item_id,
                    conversation_id,
                    seq,
                    item_type,
                    role,
                    content_json,
                    token_estimate,
                    source_start_seq,
                    source_end_seq,
                    created_at,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    conversation_id,
                    # Bug-2 fix: encode BOTH source_start_seq and source_end_seq
                    # into the synthetic seq so that two summaries with the same
                    # end seq but different start seqs cannot collide on the
                    # UNIQUE(conversation_id, seq) constraint.
                    #
                    # Formula:
                    #   1_000_000_000_000          — trillion offset, well above
                    #   + source_start_seq * 1_000_000  — any realistic raw-msg seq
                    #   + source_end_seq           — encodes the end boundary
                    #
                    # Uniqueness holds as long as both seqs stay below 10^6
                    # (i.e. no single conversation exceeds 1 000 000 messages),
                    # which is an extremely safe assumption.
                    #
                    # SQLite INTEGER is signed 64-bit (max ≈ 9.2 × 10^18);
                    # the maximum value here is ~2 × 10^12, well within range.
                    1_000_000_000_000 + source_start_seq * 1_000_000 + source_end_seq,
                    "summary_leaf",
                    "assistant",
                    payload,
                    token_estimate,
                    source_start_seq,
                    source_end_seq,
                    now,
                    "active",
                ),
            )
            await db.commit()

        return item_id

    async def write_lossless_link(
        self,
        parent_item_id: str,
        child_item_id: str,
        link_type: str,
    ) -> None:
        """Record a parent→child lineage edge in lossless_links.

        ``link_type`` should be ``"covers"`` (summary covers source messages).
        Duplicate edges are silently ignored via INSERT OR IGNORE.
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            # Add a unique constraint guard at INSERT level
            await db.execute(
                """
                INSERT OR IGNORE INTO lossless_links (
                    parent_item_id,
                    child_item_id,
                    link_type,
                    created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (parent_item_id, child_item_id, link_type, self._utcnow()),
            )
            await db.commit()

    async def update_head_after_compact(
        self,
        conversation_id: str,
        last_compacted_seq: int,
        fresh_tail_start_seq: int,
        active_summary_root_id: str,
    ) -> None:
        """Advance the per-conversation head checkpoint after a successful compaction.

        Caller is responsible for holding the per-conversation lock.
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO lossless_heads (
                    conversation_id,
                    last_ingested_seq,
                    fresh_tail_start_seq,
                    last_compacted_seq,
                    active_summary_root_id,
                    updated_at
                ) VALUES (
                    ?,
                    (SELECT last_ingested_seq FROM lossless_heads WHERE conversation_id = ?),
                    ?, ?, ?, ?
                )
                ON CONFLICT(conversation_id) DO UPDATE SET
                    last_compacted_seq      = excluded.last_compacted_seq,
                    fresh_tail_start_seq    = excluded.fresh_tail_start_seq,
                    active_summary_root_id  = excluded.active_summary_root_id,
                    updated_at              = excluded.updated_at
                """,
                (
                    conversation_id,
                    conversation_id,
                    fresh_tail_start_seq,
                    last_compacted_seq,
                    active_summary_root_id,
                    self._utcnow(),
                ),
            )
            await db.commit()

    async def get_items_by_seq_range(
        self,
        conversation_id: str,
        start_seq: int,
        end_seq: int,
    ) -> list[dict[str, Any]]:
        """Return all items whose seq is in [start_seq, end_seq] inclusive."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT
                    item_id, conversation_id, seq, item_type, role,
                    content_json, token_estimate, source_start_seq,
                    source_end_seq, created_at, status
                FROM lossless_items
                WHERE conversation_id = ?
                  AND seq >= ?
                  AND seq <= ?
                ORDER BY seq ASC
                """,
                (conversation_id, start_seq, end_seq),
            )
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_links(
        self,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        """Return all lossless_links rows whose parent item belongs to this conversation.

        Uses a JOIN through ``lossless_items`` to filter by conversation_id,
        which is robust regardless of the item_id naming convention.
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT ll.parent_item_id, ll.child_item_id, ll.link_type, ll.created_at
                FROM lossless_links ll
                JOIN lossless_items li ON ll.parent_item_id = li.item_id
                WHERE li.conversation_id = ?
                ORDER BY ll.created_at ASC
                """,
                (conversation_id,),
            )
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def list_jobs(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return recent lossless_jobs rows for a conversation."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT job_id, conversation_id, job_type, status,
                       started_at, finished_at, error, payload_json
                FROM lossless_jobs
                WHERE conversation_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (conversation_id, limit),
            )
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    def _conversation_lock(self, conversation_id: str) -> asyncio.Lock:
        if conversation_id not in self._locks:
            self._locks[conversation_id] = asyncio.Lock()
        return self._locks[conversation_id]

    def _estimate_message_tokens(self, payload: str) -> int:
        return self._token_counter._estimate_tokens(payload)

    def _item_id(self, conversation_id: str, seq: int) -> str:
        return f"{conversation_id}:{seq}"

    def _utcnow(self) -> str:
        return datetime.now(timezone.utc).isoformat()
