"""Hall collaboration API routes.

Multi-agent collaboration endpoints for real-time discussion,
task assignment, execution order management, and handoff workflows.
All routes require dashboard JWT authentication.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from quart import jsonify, request

from astrbot.core import logger
from astrbot.core.core_lifecycle import AstrBotCoreLifecycle

from .route import Response, Route, RouteContext


class HallCollaborationRoute(Route):
    def __init__(
        self,
        context: RouteContext,
        core_lifecycle: AstrBotCoreLifecycle,
    ) -> None:
        super().__init__(context)
        self._core_lifecycle = core_lifecycle
        self._star_context = core_lifecycle.star_context
        self._discussions: dict[str, list[dict]] = {}
        self._execution_orders: dict[str, dict] = {}
        self._agent_roster: list[dict] = []
        self.routes = {
            "/hall/overview": ("GET", self.get_overview),
            "/hall/discussions": ("GET", self.list_discussions),
            "/hall/discussion/<discussion_id>": ("GET", self.get_discussion),
            "/hall/discussion": ("POST", self.create_discussion),
            "/hall/discussion/<discussion_id>/message": ("POST", self.post_message),
            "/hall/discussion/<discussion_id>/assign": ("POST", self.assign_task),
            "/hall/discussion/<discussion_id>/handoff": ("POST", self.handoff_task),
            "/hall/agents": ("GET", self.get_agent_roster),
            "/hall/execution-order": ("GET", self.get_execution_order),
            "/hall/execution-order/set": ("POST", self.set_execution_order),
            "/hall/tasks/pending": ("GET", self.get_pending_tasks),
            "/hall/tasks/approvals": ("GET", self.get_approval_queue),
        }
        self.register_routes()
        self._initialize_agent_roster()

    def _initialize_agent_roster(self) -> None:
        """Initialize agent roster from current OpenClaw/Hermes configuration."""
        try:
            plugins = self._star_context.get_all_stars()
            self._agent_roster = [
                {
                    "id": getattr(plugin, "name", plugin.__class__.__name__),
                    "display_name": getattr(plugin, "name", plugin.__class__.__name__),
                    "role": self._infer_role(plugin),
                    "status": "active",
                    "capabilities": self._get_capabilities(plugin),
                }
                for plugin in plugins
            ]
            logger.info(f"Initialized agent roster with {len(self._agent_roster)} agents")
        except Exception as e:
            logger.error(f"Failed to initialize agent roster: {e}")
            self._agent_roster = []

    def _infer_role(self, plugin) -> str:
        """Infer agent role from plugin metadata."""
        name = getattr(plugin, "name", "").lower()
        if any(kw in name for kw in ["core", "main", "astr"]):
            return "coordinator"
        if any(kw in name for kw in ["knowledge", "ingest", "file"]):
            return "archivist"
        if any(kw in name for kw in ["briefing", "marketing"]):
            return "analyst"
        return "contributor"

    def _get_capabilities(self, plugin) -> list[str]:
        """Extract capabilities from plugin."""
        caps = []
        name = getattr(plugin, "name", "").lower()
        if "knowledge" in name or "ingest" in name:
            caps.extend(["file_ingest", "search", "categorize"])
        if "briefing" in name:
            caps.extend(["report", "summarize", "analyze"])
        if "core" in name:
            caps.extend(["task_manage", "memory", "permissions"])
        return caps

    async def get_overview(self) -> tuple:
        """Get hall overview with health status and summary."""
        try:
            total_discussions = len(self._discussions)
            active_tasks = sum(
                1
                for d in self._discussions.values()
                for msg in d
                if msg.get("type") == "task"
                and msg.get("status") in ["pending", "in_progress"]
            )
            pending_approvals = sum(
                1
                for d in self._discussions.values()
                for msg in d
                if msg.get("type") == "task" and msg.get("status") == "pending_review"
            )

            return (
                jsonify(
                    Response()
                    .ok(
                        data={
                            "health": "healthy",
                            "total_agents": len(self._agent_roster),
                            "total_discussions": total_discussions,
                            "active_tasks": active_tasks,
                            "pending_approvals": pending_approvals,
                            "recent_activity": self._get_recent_activity(),
                        }
                    )
                    .__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error getting hall overview: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def list_discussions(self) -> tuple:
        """List all discussions with summaries."""
        try:
            limit = request.args.get("limit", 20, type=int)
            offset = request.args.get("offset", 0, type=int)

            discussions = []
            for disc_id, messages in list(self._discussions.items())[
                offset : offset + limit
            ]:
                last_msg = messages[-1] if messages else None
                discussions.append(
                    {
                        "id": disc_id,
                        "message_count": len(messages),
                        "last_activity": (
                            last_msg.get("timestamp") if last_msg else None
                        ),
                        "participants": list(
                            {msg.get("author") for msg in messages}
                        ),
                        "has_pending_tasks": any(
                            msg.get("type") == "task"
                            and msg.get("status") in ["pending", "in_progress"]
                            for msg in messages
                        ),
                    }
                )

            return (
                jsonify(
                    Response()
                    .ok(
                        data={
                            "discussions": discussions,
                            "total": len(self._discussions),
                            "limit": limit,
                            "offset": offset,
                        }
                    )
                    .__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error listing discussions: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_discussion(self, discussion_id: str) -> tuple:
        """Get full discussion with all messages."""
        try:
            if discussion_id not in self._discussions:
                return (
                    jsonify(Response().error("Discussion not found").__dict__),
                    404,
                )

            messages = self._discussions[discussion_id]
            return (
                jsonify(
                    Response()
                    .ok(
                        data={
                            "id": discussion_id,
                            "messages": messages,
                            "message_count": len(messages),
                        }
                    )
                    .__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error getting discussion: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def create_discussion(self) -> tuple:
        """Create a new discussion thread."""
        try:
            data = await request.get_json(silent=True)
            if not data:
                return (
                    jsonify(Response().error("Request body required").__dict__),
                    400,
                )

            title = data.get("title", "Untitled Discussion")
            author = data.get("author", "system")
            initial_message = data.get("message", "")

            discussion_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            messages = [
                {
                    "id": str(uuid.uuid4()),
                    "type": "system",
                    "author": "system",
                    "content": f"Discussion created: {title}",
                    "timestamp": timestamp,
                }
            ]

            if initial_message:
                messages.append(
                    {
                        "id": str(uuid.uuid4()),
                        "type": "message",
                        "author": author,
                        "content": initial_message,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

            self._discussions[discussion_id] = messages

            logger.info(f"Created discussion {discussion_id}: {title}")

            return (
                jsonify(
                    Response()
                    .ok(
                        data={
                            "id": discussion_id,
                            "title": title,
                            "message_count": len(messages),
                            "created_at": timestamp,
                        }
                    )
                    .__dict__
                ),
                201,
            )
        except Exception as exc:
            logger.error(f"Error creating discussion: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def post_message(self, discussion_id: str) -> tuple:
        """Post a message to a discussion."""
        try:
            if discussion_id not in self._discussions:
                return (
                    jsonify(Response().error("Discussion not found").__dict__),
                    404,
                )

            data = await request.get_json(silent=True)
            if not data:
                return (
                    jsonify(Response().error("Request body required").__dict__),
                    400,
                )

            message = {
                "id": str(uuid.uuid4()),
                "type": data.get("type", "message"),
                "author": data.get("author", "anonymous"),
                "content": data.get("content", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if data.get("type") == "task":
                message.update(
                    {
                        "task_type": data.get("task_type", "general"),
                        "status": "pending",
                        "assignee": data.get("assignee"),
                        "priority": data.get("priority", "medium"),
                        "metadata": data.get("metadata", {}),
                    }
                )

            self._discussions[discussion_id].append(message)

            return (
                jsonify(Response().ok(data=message).__dict__),
                201,
            )
        except Exception as exc:
            logger.error(f"Error posting message: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def assign_task(self, discussion_id: str) -> tuple:
        """Assign a task to an agent."""
        try:
            data = await request.get_json(silent=True)
            if not data:
                return (
                    jsonify(Response().error("Request body required").__dict__),
                    400,
                )

            message_id = data.get("message_id")
            assignee = data.get("assignee")

            if not message_id or not assignee:
                return (
                    jsonify(
                        Response().error("message_id and assignee required").__dict__
                    ),
                    400,
                )

            if discussion_id not in self._discussions:
                return (
                    jsonify(Response().error("Discussion not found").__dict__),
                    404,
                )

            for msg in self._discussions[discussion_id]:
                if msg.get("id") == message_id:
                    msg["assignee"] = assignee
                    msg["status"] = "assigned"
                    msg["assigned_at"] = datetime.now(timezone.utc).isoformat()
                    break

            logger.info(f"Assigned task {message_id} in {discussion_id} to {assignee}")

            return (
                jsonify(Response().ok(data={"assigned_to": assignee}).__dict__),
                200,
            )
        except Exception as exc:
            logger.error(f"Error assigning task: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def handoff_task(self, discussion_id: str) -> tuple:
        """Hand off a task to another agent with context transfer."""
        try:
            data = await request.get_json(silent=True)
            if not data:
                return (
                    jsonify(Response().error("Request body required").__dict__),
                    400,
                )

            message_id = data.get("message_id")
            new_owner = data.get("new_owner")
            handoff_notes = data.get("handoff_notes", "")

            if not message_id or not new_owner:
                return (
                    jsonify(
                        Response().error("message_id and new_owner required").__dict__
                    ),
                    400,
                )

            if discussion_id not in self._discussions:
                return (
                    jsonify(Response().error("Discussion not found").__dict__),
                    404,
                )

            handoff_record = None
            for msg in self._discussions[discussion_id]:
                if msg.get("id") == message_id:
                    previous_owner = msg.get("assignee")
                    msg["assignee"] = new_owner
                    msg["status"] = "handed_off"
                    msg["handoff_context"] = {
                        "previous_owner": previous_owner,
                        "new_owner": new_owner,
                        "handoff_notes": handoff_notes,
                        "handoff_time": datetime.now(timezone.utc).isoformat(),
                    }

                    handoff_record = msg
                    break

            if handoff_record:
                self._discussions[discussion_id].append(
                    {
                        "id": str(uuid.uuid4()),
                        "type": "handoff",
                        "author": "system",
                        "content": f"Task handed off from {previous_owner} to {new_owner}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "references": [message_id],
                    }
                )

            logger.info(
                f"Handed off task {message_id} from {previous_owner} to {new_owner}"
            )

            return (
                jsonify(
                    Response().ok(data={"handoff_record": handoff_record}).__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error handing off task: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_agent_roster(self) -> tuple:
        """Get current agent roster with roles and capabilities."""
        try:
            self._initialize_agent_roster()
            return (
                jsonify(
                    Response()
                    .ok(
                        data={
                            "agents": self._agent_roster,
                            "total": len(self._agent_roster),
                        }
                    )
                    .__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error getting agent roster: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_execution_order(self) -> tuple:
        """Get execution order for a discussion."""
        try:
            discussion_id = request.args.get("discussion_id")

            if not discussion_id:
                return (
                    jsonify(Response().ok(data=self._execution_orders).__dict__),
                    200,
                )

            if discussion_id not in self._execution_orders:
                return (
                    jsonify(Response().error("Execution order not set").__dict__),
                    404,
                )

            return (
                jsonify(
                    Response().ok(
                        data=self._execution_orders[discussion_id]
                    ).__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error getting execution order: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def set_execution_order(self) -> tuple:
        """Set execution order for a discussion."""
        try:
            data = await request.get_json(silent=True)
            if not data:
                return (
                    jsonify(Response().error("Request body required").__dict__),
                    400,
                )

            discussion_id = data.get("discussion_id")
            order = data.get("order", [])

            if not discussion_id:
                return (
                    jsonify(Response().error("discussion_id required").__dict__),
                    400,
                )

            self._execution_orders[discussion_id] = {
                "discussion_id": discussion_id,
                "order": order,
                "current_index": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"Set execution order for discussion {discussion_id}")

            return (
                jsonify(
                    Response().ok(data=self._execution_orders[discussion_id]).__dict__
                ),
                201,
            )
        except Exception as exc:
            logger.error(f"Error setting execution order: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_pending_tasks(self) -> tuple:
        """Get all pending tasks across discussions."""
        try:
            pending_tasks = []
            for disc_id, messages in self._discussions.items():
                for msg in messages:
                    if msg.get("type") == "task" and msg.get("status") in [
                        "pending",
                        "assigned",
                        "in_progress",
                    ]:
                        pending_tasks.append(
                            {
                                **msg,
                                "discussion_id": disc_id,
                            }
                        )

            pending_tasks.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            return (
                jsonify(
                    Response()
                    .ok(
                        data={
                            "tasks": pending_tasks[:50],
                            "total": len(pending_tasks),
                        }
                    )
                    .__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error getting pending tasks: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_approval_queue(self) -> tuple:
        """Get tasks pending review/approval."""
        try:
            approval_tasks = []
            for disc_id, messages in self._discussions.items():
                for msg in messages:
                    if msg.get("type") == "task" and msg.get("status") in [
                        "pending_review",
                        "blocked",
                    ]:
                        approval_tasks.append({**msg, "discussion_id": disc_id})

            approval_tasks.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            return (
                jsonify(
                    Response()
                    .ok(
                        data={
                            "approvals": approval_tasks[:20],
                            "total": len(approval_tasks),
                        }
                    )
                    .__dict__
                ),
                200,
            )
        except Exception as exc:
            logger.error(f"Error getting approval queue: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    def _get_recent_activity(self, limit: int = 10) -> list[dict]:
        """Get recent activity across all discussions."""
        activities = []
        for disc_id, messages in self._discussions.items():
            for msg in messages[-limit:]:
                activities.append(
                    {
                        **msg,
                        "discussion_id": disc_id,
                    }
                )

        activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return activities[:limit]
