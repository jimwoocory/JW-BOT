"""Harness debug API routes.

Read-only inspection endpoints for Harness task and event traces.
Includes execution chain visualization and approval workflow endpoints.
All routes require dashboard JWT authentication.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from quart import jsonify, request

from astrbot.core import logger
from astrbot.core.core_lifecycle import AstrBotCoreLifecycle

from .route import Response, Route, RouteContext


@dataclass
class ExecutionStep:
    """Represents a step in the execution chain."""

    id: str
    task_id: str
    step_type: str
    status: str
    agent: str | None = None
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int = 0
    error: str | None = None


@dataclass
class ApprovalRequest:
    """Represents an approval request in the workflow."""

    id: str
    task_id: str
    requester: str
    reviewer: str | None = None
    status: str = "pending"
    created_at: str | None = None
    reviewed_at: str | None = None
    decision: str | None = None
    comments: str | None = None
    evidence_urls: list[str] | None = None


class HarnessDebugRoute(Route):
    def __init__(
        self,
        context: RouteContext,
        core_lifecycle: AstrBotCoreLifecycle,
    ) -> None:
        super().__init__(context)
        self._store = core_lifecycle.harness_store
        self._execution_chains: dict[str, list[ExecutionStep]] = {}
        self._approvals: dict[str, ApprovalRequest] = {}
        self.routes = {
            "/harness/tasks/<conversation_id>": ("GET", self.list_tasks),
            "/harness/task/<task_id>": ("GET", self.get_task),
            "/harness/task/<task_id>/events": ("GET", self.list_events),
            "/harness/task/<task_id>/reviews": ("GET", self.list_reviews),
            "/harness/execution-chain/<task_id>": ("GET", self.get_execution_chain),
            "/harness/approvals": ("GET", self.list_approvals),
            "/harness/approval/<approval_id>": ("GET", self.get_approval),
            "/harness/approval/<approval_id>/review": ("POST", self.review_approval),
            "/harness/overview": ("GET", self.get_overview),
        }
        self.register_routes()

    async def list_tasks(self, conversation_id: str) -> tuple:
        """List all tasks for a conversation with execution metadata."""
        try:
            if self._store is None:
                return (
                    jsonify(Response().error("Harness store unavailable").__dict__),
                    503,
                )

            limit = request.args.get("limit", 20, type=int)
            tasks = await self._store.list_tasks_for_conversation(
                conversation_id,
                limit=limit,
            )

            tasks_with_metadata = []
            for task in tasks:
                task_dict = asdict(task)
                task_dict["has_execution_chain"] = task.id in self._execution_chains
                task_dict["has_pending_approval"] = any(
                    a.task_id == task.id and a.status == "pending"
                    for a in self._approvals.values()
                )
                tasks_with_metadata.append(task_dict)

            return jsonify(
                Response()
                .ok(
                    data={
                        "conversation_id": conversation_id,
                        "tasks": tasks_with_metadata,
                        "limit": limit,
                        "total": len(tasks_with_metadata),
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error listing harness tasks: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_task(self, task_id: str) -> tuple:
        """Get detailed task information with execution context."""
        try:
            if self._store is None:
                return (
                    jsonify(Response().error("Harness store unavailable").__dict__),
                    503,
                )

            task = await self._store.get_task(task_id)
            if task is None:
                return (
                    jsonify(Response().error("Task not found").__dict__),
                    404,
                )

            task_dict = asdict(task)
            task_dict["execution_chain"] = [
                asdict(step) for step in self._execution_chains.get(task_id, [])
            ]
            task_dict["approvals"] = [
                asdict(approval)
                for approval in self._approvals.values()
                if approval.task_id == task_id
            ]

            return jsonify(Response().ok(data=task_dict).__dict__)
        except Exception as exc:
            logger.error(f"Error getting harness task: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def list_events(self, task_id: str) -> tuple:
        """List all events for a task with timeline visualization data."""
        try:
            if self._store is None:
                return (
                    jsonify(Response().error("Harness store unavailable").__dict__),
                    503,
                )

            events = await self._store.list_events(task_id)

            events_with_timeline = []
            prev_timestamp = None
            for event in events:
                event_dict = asdict(event)
                if hasattr(event, "timestamp") and prev_timestamp:
                    event_dict["time_from_previous"] = (
                        (event.timestamp - prev_timestamp).total_seconds() * 1000
                        if isinstance(prev_timestamp, datetime)
                        else 0
                    )
                if hasattr(event, "timestamp"):
                    prev_timestamp = event.timestamp
                events_with_timeline.append(event_dict)

            return jsonify(
                Response()
                .ok(
                    data={
                        "task_id": task_id,
                        "events": events_with_timeline,
                        "total_events": len(events_with_timeline),
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error listing harness events: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def list_reviews(self, task_id: str) -> tuple:
        """List all reviews for a task with decision details."""
        try:
            if self._store is None:
                return (
                    jsonify(Response().error("Harness store unavailable").__dict__),
                    503,
                )

            reviews = await self._store.list_reviews(task_id)

            reviews_enhanced = []
            for review in reviews:
                review_dict = asdict(review)
                review_dict["evidence_available"] = bool(
                    getattr(review, "evidence_urls", None)
                )
                reviews_enhanced.append(review_dict)

            return jsonify(
                Response()
                .ok(
                    data={
                        "task_id": task_id,
                        "reviews": reviews_enhanced,
                        "total_reviews": len(reviews_enhanced),
                        "approved_count": sum(
                            1
                            for r in reviews
                            if getattr(r, "decision", "") == "approved"
                        ),
                        "rejected_count": sum(
                            1
                            for r in reviews
                            if getattr(r, "decision", "") == "rejected"
                        ),
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error listing harness reviews: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_execution_chain(self, task_id: str) -> tuple:
        """Get execution chain visualization for a task."""
        try:
            if task_id not in self._execution_chains:
                return (
                    jsonify(Response().error("Execution chain not found").__dict__),
                    404,
                )

            chain = self._execution_chains[task_id]
            chain_dicts = [asdict(step) for step in chain]

            total_duration = sum(s.duration_ms for s in chain)
            completed_steps = sum(1 for s in chain if s.status == "completed")
            failed_steps = sum(1 for s in chain if s.status == "failed")

            return jsonify(
                Response()
                .ok(
                    data={
                        "task_id": task_id,
                        "chain": chain_dicts,
                        "summary": {
                            "total_steps": len(chain),
                            "completed_steps": completed_steps,
                            "failed_steps": failed_steps,
                            "in_progress_steps": sum(
                                1 for s in chain if s.status == "running"
                            ),
                            "total_duration_ms": total_duration,
                            "average_step_duration_ms": (
                                total_duration / max(completed_steps, 1)
                            ),
                            "success_rate": (
                                completed_steps / max(len(chain), 1) * 100
                            ),
                        },
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error getting execution chain: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def list_approvals(self) -> tuple:
        """List all pending and recent approvals."""
        try:
            status_filter = request.args.get("status")
            limit = request.args.get("limit", 20, type=int)

            approvals_list = list(self._approvals.values())

            if status_filter:
                approvals_list = [
                    a for a in approvals_list if a.status == status_filter
                ]

            approvals_list.sort(key=lambda x: x.created_at or "", reverse=True)

            paginated_approvals = approvals_list[:limit]

            return jsonify(
                Response()
                .ok(
                    data={
                        "approvals": [asdict(a) for a in paginated_approvals],
                        "total": len(approvals_list),
                        "pending_count": sum(
                            1 for a in approvals_list if a.status == "pending"
                        ),
                        "approved_count": sum(
                            1 for a in approvals_list if a.status == "approved"
                        ),
                        "rejected_count": sum(
                            1 for a in approvals_list if a.status == "rejected"
                        ),
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error listing approvals: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_approval(self, approval_id: str) -> tuple:
        """Get detailed approval information."""
        try:
            if approval_id not in self._approvals:
                return (
                    jsonify(Response().error("Approval not found").__dict__),
                    404,
                )

            approval = self._approvals[approval_id]
            return jsonify(Response().ok(data=asdict(approval)).__dict__)
        except Exception as exc:
            logger.error(f"Error getting approval: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def review_approval(self, approval_id: str) -> tuple:
        """Submit an approval or rejection decision."""
        try:
            if approval_id not in self._approvals:
                return (
                    jsonify(Response().error("Approval not found").__dict__),
                    404,
                )

            data = await request.get_json(silent=True)
            if not data:
                return (
                    jsonify(Response().error("Request body required").__dict__),
                    400,
                )

            decision = data.get("decision")
            reviewer = data.get("reviewer")
            comments = data.get("comments", "")

            if decision not in ["approved", "rejected"]:
                return (
                    jsonify(
                        Response()
                        .error('decision must be "approved" or "rejected"')
                        .__dict__
                    ),
                    400,
                )

            approval = self._approvals[approval_id]
            approval.reviewer = reviewer
            approval.decision = decision
            approval.status = decision
            approval.comments = comments
            approval.reviewed_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"Approval {approval_id} {decision} by {reviewer}")

            return jsonify(
                Response().ok(data={"status": "reviewed", **asdict(approval)}).__dict__
            )
        except Exception as exc:
            logger.error(f"Error reviewing approval: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_overview(self) -> tuple:
        """Get harness system overview with statistics."""
        try:
            total_tasks = len(self._execution_chains)
            total_approvals = len(self._approvals)
            pending_approvals = sum(
                1 for a in self._approvals.values() if a.status == "pending"
            )

            active_executions = sum(
                1
                for chain in self._execution_chains.values()
                if any(s.status == "running" for s in chain)
            )

            return jsonify(
                Response()
                .ok(
                    data={
                        "health": "operational",
                        "statistics": {
                            "total_execution_chains": total_tasks,
                            "active_executions": active_executions,
                            "total_approvals": total_approvals,
                            "pending_approvals": pending_approvals,
                            "approval_queue_depth": pending_approvals,
                        },
                        "recent_activity": self._get_recent_activity(),
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error getting harness overview: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    def _get_recent_activity(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent harness activity across all tasks and approvals."""
        activities = []

        for task_id, chain in self._execution_chains.items():
            if chain:
                last_step = chain[-1]
                activities.append(
                    {
                        "type": "execution",
                        "task_id": task_id,
                        "step_type": last_step.step_type,
                        "status": last_step.status,
                        "timestamp": last_step.completed_at or last_step.started_at,
                    }
                )

        for approval in self._approvals.values():
            activities.append(
                {
                    "type": "approval",
                    "approval_id": approval.id,
                    "task_id": approval.task_id,
                    "status": approval.status,
                    "timestamp": approval.created_at,
                }
            )

        activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return activities[:limit]

    # Helper methods to create execution chains and approvals programmatically

    def create_execution_chain(self, task_id: str, steps: list[dict[str, Any]]) -> None:
        """Create an execution chain for a task."""
        chain = []
        for step_data in steps:
            step = ExecutionStep(
                id=str(uuid.uuid4()),
                task_id=task_id,
                step_type=step_data.get("type", "unknown"),
                status=step_data.get("status", "pending"),
                agent=step_data.get("agent"),
                input_data=step_data.get("input"),
                output_data=step_data.get("output"),
                started_at=step_data.get("started_at"),
                completed_at=step_data.get("completed_at"),
                duration_ms=step_data.get("duration_ms", 0),
                error=step_data.get("error"),
            )
            chain.append(step)

        self._execution_chains[task_id] = chain
        logger.info(
            f"Created execution chain for task {task_id} with {len(chain)} steps"
        )

    def create_approval_request(
        self,
        task_id: str,
        requester: str,
        evidence_urls: list[str] | None = None,
    ) -> str:
        """Create an approval request for a task."""
        approval_id = str(uuid.uuid4())
        approval = ApprovalRequest(
            id=approval_id,
            task_id=task_id,
            requester=requester,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            evidence_urls=evidence_urls,
        )

        self._approvals[approval_id] = approval
        logger.info(f"Created approval request {approval_id} for task {task_id}")

        return approval_id
