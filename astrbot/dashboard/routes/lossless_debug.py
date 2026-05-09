"""Lossless context debug API routes.

Provides read-only inspection endpoints for the sidecar store.
All routes require dashboard JWT authentication (enforced by the global
``auth_middleware`` in ``AstrBotDashboard``).

Endpoints
---------
GET /api/lossless/heads/<conversation_id>
    Return the lossless_heads row for a conversation.

GET /api/lossless/items/<conversation_id>?limit=50&offset=0
    Return lossless_items rows (raw messages + summary nodes).

GET /api/lossless/links/<conversation_id>
    Return lossless_links lineage rows.

GET /api/lossless/jobs/<conversation_id>?limit=20
    Return recent lossless_jobs rows.
"""

from __future__ import annotations

import asyncio

from quart import jsonify, request

from astrbot.core.core_lifecycle import AstrBotCoreLifecycle

from .route import Response, Route, RouteContext


class LosslessDebugRoute(Route):
    def __init__(
        self,
        context: RouteContext,
        core_lifecycle: AstrBotCoreLifecycle,
    ) -> None:
        super().__init__(context)
        self._store = core_lifecycle.conversation_manager.lossless_store
        self.routes = {
            "/lossless/heads/<conversation_id>": ("GET", self.get_head),
            "/lossless/items/<conversation_id>": ("GET", self.list_items),
            "/lossless/links/<conversation_id>": ("GET", self.get_links),
            "/lossless/jobs/<conversation_id>": ("GET", self.list_jobs),
        }
        self.register_routes()

    async def get_head(self, conversation_id: str):
        """Return the lossless_heads row for a conversation."""
        try:
            head = await self._store.get_head(conversation_id)
            return jsonify(
                Response()
                .ok(
                    data={
                        "conversation_id": head.conversation_id,
                        "last_ingested_seq": head.last_ingested_seq,
                        "fresh_tail_start_seq": head.fresh_tail_start_seq,
                        "last_compacted_seq": head.last_compacted_seq,
                        "active_summary_root_id": head.active_summary_root_id,
                    }
                )
                .__dict__
            )
        except Exception as exc:
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def list_items(self, conversation_id: str):
        """Return lossless_items rows with correct pagination metadata."""
        try:
            limit = request.args.get("limit", 50, type=int)
            offset = request.args.get("offset", 0, type=int)
            total, items = await asyncio.gather(
                self._store.count_items(conversation_id),
                self._store.list_items(conversation_id, limit=limit, offset=offset),
            )
            return jsonify(
                Response()
                .ok(
                    data={
                        "items": items,
                        "total": total,
                        "offset": offset,
                        "limit": limit,
                    }
                )
                .__dict__
            )
        except Exception as exc:
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_links(self, conversation_id: str):
        """Return lossless_links lineage rows."""
        try:
            links = await self._store.get_links(conversation_id)
            return jsonify(Response().ok(data={"links": links}).__dict__)
        except Exception as exc:
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def list_jobs(self, conversation_id: str):
        """Return recent lossless_jobs rows."""
        try:
            limit = request.args.get("limit", 20, type=int)
            jobs = await self._store.list_jobs(conversation_id, limit=limit)
            return jsonify(Response().ok(data={"jobs": jobs}).__dict__)
        except Exception as exc:
            return jsonify(Response().error(str(exc)).__dict__), 500
