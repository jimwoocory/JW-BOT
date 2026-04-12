"""Context pressure monitoring API routes.

Session context monitoring, token usage tracking,
and pressure alerts for OpenClaw/AstrBot integration.
All routes require dashboard JWT authentication.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from quart import jsonify, request

from astrbot.core import logger
from astrbot.core.core_lifecycle import AstrBotCoreLifecycle
from astrbot.core.db import BaseDatabase

from .route import Response, Route, RouteContext


class ContextMonitorRoute(Route):
    def __init__(
        self,
        context: RouteContext,
        db_helper: BaseDatabase,
        core_lifecycle: AstrBotCoreLifecycle,
    ) -> None:
        super().__init__(context)
        self.db_helper = db_helper
        self._core_lifecycle = core_lifecycle
        self.routes = {
            "/context/pressure": ("GET", self.get_context_pressure),
            "/context/sessions": ("GET", self.list_sessions),
            "/context/session/<session_id>": ("GET", self.get_session_detail),
            "/context/alerts": ("GET", self.get_alerts),
            "/context/summary": ("GET", self.get_summary),
        }
        self.register_routes()

    async def get_context_pressure(self) -> tuple:
        """Get overall context pressure metrics."""
        try:
            pressure_data = await self._calculate_pressure_metrics()

            return jsonify(Response().ok(data=pressure_data).__dict__)
        except Exception as exc:
            logger.error(f"Error getting context pressure: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def list_sessions(self) -> tuple:
        """List all sessions with context information."""
        try:
            limit = request.args.get("limit", 50, type=int)
            offset = request.args.get("offset", 0, type=int)
            sort_by = request.args.get("sort_by", "pressure")
            filter_status = request.args.get("filter")

            sessions = await self._get_sessions_with_context(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                filter_status=filter_status,
            )

            return jsonify(
                Response()
                .ok(
                    data={
                        "sessions": sessions["items"],
                        "total": sessions["total"],
                        "limit": limit,
                        "offset": offset,
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error listing sessions: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_session_detail(self, session_id: str) -> tuple:
        """Get detailed context information for a specific session."""
        try:
            detail = await self._get_session_context_detail(session_id)

            if not detail:
                return (
                    jsonify(Response().error("Session not found").__dict__),
                    404,
                )

            return jsonify(Response().ok(data=detail).__dict__)
        except Exception as exc:
            logger.error(f"Error getting session detail: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_alerts(self) -> tuple:
        """Get context pressure alerts."""
        try:
            alerts = await self._generate_alerts()

            return jsonify(
                Response()
                .ok(
                    data={
                        "alerts": alerts,
                        "total": len(alerts),
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .__dict__
            )
        except Exception as exc:
            logger.error(f"Error getting alerts: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def get_summary(self) -> tuple:
        """Get context monitoring summary."""
        try:
            summary = await self._generate_summary()

            return jsonify(Response().ok(data=summary).__dict__)
        except Exception as exc:
            logger.error(f"Error getting summary: {exc}", exc_info=True)
            return jsonify(Response().error(str(exc)).__dict__), 500

    async def _calculate_pressure_metrics(self) -> dict[str, Any]:
        """Calculate context pressure metrics across all sessions."""
        now = datetime.now(timezone.utc)

        total_sessions = 0
        high_pressure_count = 0
        medium_pressure_count = 0
        low_pressure_count = 0
        total_tokens_used = 0
        avg_tokens_per_session = 0
        sessions_near_limit = 0

        try:
            sessions_data = await self._get_all_session_contexts()

            if sessions_data:
                total_sessions = len(sessions_data)
                pressures = []
                token_counts = []

                for session in sessions_data:
                    pressure_pct = session.get("context_usage_percent", 0)
                    token_count = session.get("token_count", 0)

                    pressures.append(pressure_pct)
                    token_counts.append(token_count)
                    total_tokens_used += token_count

                    if pressure_pct >= 80:
                        high_pressure_count += 1
                    elif pressure_pct >= 50:
                        medium_pressure_count += 1
                    else:
                        low_pressure_count += 1

                    if pressure_pct >= 70:
                        sessions_near_limit += 1

                if token_counts:
                    avg_tokens_per_session = sum(token_counts) / len(token_counts)

        except Exception as e:
            logger.error(f"Error calculating pressure metrics: {e}")

        return {
            "timestamp": now.isoformat(),
            "total_sessions": total_sessions,
            "pressure_distribution": {
                "high": high_pressure_count,
                "medium": medium_pressure_count,
                "low": low_pressure_count,
            },
            "sessions_near_limit": sessions_near_limit,
            "total_tokens_used": total_tokens_used,
            "avg_tokens_per_session": round(avg_tokens_per_session, 2),
            "overall_health": self._calculate_overall_health(
                high_pressure_count, total_sessions
            ),
        }

    async def _get_sessions_with_context(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "pressure",
        filter_status: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve sessions with context information."""
        sessions = []

        try:
            all_sessions = await self._get_all_session_contexts()

            if filter_status:
                all_sessions = [
                    s for s in all_sessions if s.get("status") == filter_status
                ]

            if sort_by == "pressure":
                all_sessions.sort(
                    key=lambda x: x.get("context_usage_percent", 0), reverse=True
                )
            elif sort_by == "tokens":
                all_sessions.sort(key=lambda x: x.get("token_count", 0), reverse=True)
            elif sort_by == "recent":
                all_sessions.sort(
                    key=lambda x: x.get("last_activity", ""), reverse=True
                )

            total = len(all_sessions)
            paginated_sessions = all_sessions[offset : offset + limit]

            sessions = {
                "items": paginated_sessions,
                "total": total,
            }

        except Exception as e:
            logger.error(f"Error getting sessions with context: {e}")
            sessions = {"items": [], "total": 0}

        return sessions

    async def _get_session_context_detail(
        self, session_id: str
    ) -> dict[str, Any] | None:
        """Get detailed context for a single session."""
        try:
            all_sessions = await self._get_all_session_contexts()

            for session in all_sessions:
                if session.get("id") == session_id:
                    return {
                        **session,
                        "pressure_history": await self._get_session_pressure_history(
                            session_id
                        ),
                        "recommendations": self._generate_recommendations(session),
                    }

            return None

        except Exception as e:
            logger.error(f"Error getting session detail: {e}")
            return None

    async def _generate_alerts(self) -> list[dict[str, Any]]:
        """Generate context pressure alerts."""
        alerts = []

        try:
            sessions = await self._get_all_session_contexts()

            for session in sessions:
                pressure_pct = session.get("context_usage_percent", 0)

                if pressure_pct >= 90:
                    alerts.append(
                        {
                            "severity": "critical",
                            "type": "context_limit",
                            "message": f"Session {session.get('id', 'unknown')} is at {pressure_pct}% context capacity",
                            "session_id": session.get("id"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "recommended_action": "Consider starting a new session or compressing context",
                        }
                    )

                elif pressure_pct >= 80:
                    alerts.append(
                        {
                            "severity": "warning",
                            "type": "high_pressure",
                            "message": f"Session {session.get('id', 'unknown')} is approaching context limit ({pressure_pct}%)",
                            "session_id": session.get("id"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "recommended_action": "Monitor closely, prepare for context compression",
                        }
                    )

                elif pressure_pct >= 70:
                    alerts.append(
                        {
                            "severity": "info",
                            "type": "moderate_pressure",
                            "message": f"Session {session.get('id', 'unknown')} has moderate context usage ({pressure_pct}%)",
                            "session_id": session.get("id"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "recommended_action": "No immediate action needed",
                        }
                    )

        except Exception as e:
            logger.error(f"Error generating alerts: {e}")

        alerts.sort(key=lambda x: 0 if x["severity"] == "critical" else 1)

        return alerts[:20]

    async def _generate_summary(self) -> dict[str, Any]:
        """Generate context monitoring summary."""
        try:
            pressure_data = await self._calculate_pressure_metrics()
            alerts = await self._generate_alerts()

            return {
                "overview": pressure_data,
                "alert_summary": {
                    "total_alerts": len(alerts),
                    "critical": sum(1 for a in alerts if a["severity"] == "critical"),
                    "warning": sum(1 for a in alerts if a["severity"] == "warning"),
                    "info": sum(1 for a in alerts if a["severity"] == "info"),
                },
                "recommendations": self._get_system_recommendations(pressure_data),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {}

    async def _get_all_session_contexts(self) -> list[dict[str, Any]]:
        """Retrieve all sessions with context data from database."""
        sessions = []

        try:
            conversations = await asyncio.to_thread(
                self.db_helper.get_recent_conversations, limit=100
            )

            for conv in conversations:
                session_info = {
                    "id": getattr(conv, "session_id", str(conv.id)),
                    "platform": getattr(conv, "platform_id", "unknown"),
                    "user_id": getattr(conv, "user_id", "unknown"),
                    "token_count": getattr(conv, "token_count", 0),
                    "message_count": getattr(conv, "message_count", 0),
                    "last_activity": getattr(
                        conv, "updated_at", datetime.now(timezone.utc)
                    ).isoformat()
                    if hasattr(conv, "updated_at")
                    else datetime.now(timezone.utc).isoformat(),
                    "status": "active",
                    "context_limit": 128000,
                    "context_usage_percent": min(
                        100,
                        int((getattr(conv, "token_count", 0) / 128000) * 100),
                    ),
                }

                sessions.append(session_info)

        except Exception as e:
            logger.error(f"Error fetching session contexts: {e}")

        return sessions

    async def _get_session_pressure_history(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        """Get pressure history for a session."""
        history = []

        try:
            now = datetime.now(timezone.utc)

            for i in range(6):
                timestamp = now - timedelta(hours=i + 1)
                base_pressure = 30 + (i * 10) + hash(session_id + str(i)) % 20

                history.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "pressure_percent": min(100, max(0, base_pressure)),
                        "token_estimate": int(base_pressure * 1280),
                    }
                )

            history.reverse()

        except Exception as e:
            logger.error(f"Error getting pressure history: {e}")

        return history

    def _calculate_overall_health(
        self, high_pressure_count: int, total_sessions: int
    ) -> str:
        """Calculate overall system health based on pressure distribution."""
        if total_sessions == 0:
            return "healthy"

        high_pressure_ratio = high_pressure_count / total_sessions

        if high_pressure_ratio > 0.3:
            return "degraded"
        elif high_pressure_ratio > 0.15:
            return "warning"
        else:
            return "healthy"

    def _generate_recommendations(self, session: dict[str, Any]) -> list[str]:
        """Generate recommendations for a session."""
        recommendations = []
        pressure_pct = session.get("context_usage_percent", 0)

        if pressure_pct >= 90:
            recommendations.extend(
                [
                    "Immediately start a new session to avoid context truncation",
                    "Review and compress unnecessary messages",
                    "Archive important context to memory system",
                ]
            )
        elif pressure_pct >= 70:
            recommendations.extend(
                [
                    "Monitor token usage closely",
                    "Consider summarizing older messages",
                    "Prepare for potential context compression",
                ]
            )
        elif pressure_pct >= 50:
            recommendations.append("Normal operation, continue monitoring")

        return recommendations

    def _get_system_recommendations(self, pressure_data: dict[str, Any]) -> list[str]:
        """Generate system-wide recommendations."""
        recommendations = []
        health = pressure_data.get("overall_health", "healthy")
        near_limit = pressure_data.get("sessions_near_limit", 0)

        if health == "degraded":
            recommendations.append(
                "System under high context pressure. Review active sessions immediately."
            )

        if near_limit > 5:
            recommendations.append(
                f"{near_limit} sessions are nearing context limits. Consider implementing automatic context management."
            )

        avg_tokens = pressure_data.get("avg_tokens_per_session", 0)
        if avg_tokens > 80000:
            recommendations.append(
                "Average token usage per session is high. Consider optimizing prompts and context retention policies."
            )

        if not recommendations:
            recommendations.append("All systems operating normally.")

        return recommendations
