from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp

from astrbot.core import logger
from astrbot.core.group_summary import (
    fetch_group_messages,
    format_summary,
    parse_time_range,
    summarize_group_chat,
)
from astrbot.core.group_summary.history_fetcher import UnsupportedPlatformError
from astrbot.core.harness import create_workflow_request
from astrbot.core.harness.satisfaction import SatisfactionDetector, SatisfactionSignal
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.core.pipeline.context import PipelineContext
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.router import Intent, IntentRouter
from astrbot.core.router_decision_logger import (
    RouterDecisionLogger,
    build_decision_record,
)
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.filter.permission import PermissionTypeFilter
from astrbot.core.star.session_plugin_manager import SessionPluginManager
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import EventType, star_handlers_registry
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


class RouterStage:
    def __init__(self) -> None:
        self.ctx: PipelineContext | None = None
        self.router: IntentRouter | None = None
        self.decision_logger: RouterDecisionLogger | None = None
        self._satisfaction_detector = SatisfactionDetector()

    async def initialize(self, ctx: PipelineContext) -> None:
        self.ctx = ctx
        config_path = Path(__file__).resolve().parents[2] / "router_config.yaml"
        self.router = IntentRouter.from_yaml(
            config_path,
            llm_provider=self._classify_with_llm,
        )
        # Phase R0.2: 落盘每条路由决策，供 benchmark / clarify 回写 / 漂移监控消费。
        try:
            self.decision_logger = RouterDecisionLogger(
                Path(get_astrbot_data_path()) / "router_decisions.jsonl",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[RouterStage] 决策日志初始化失败：%s", exc)
            self.decision_logger = None

    async def route(self, event: AstrMessageEvent) -> bool:
        if self.ctx is None or self.router is None:
            return False

        if event.get_extra("activated_handlers", []):
            return False

        # Check dissatisfaction before normal intent routing so an active task can escalate.
        if await self._check_hermes_escalation(event):
            return True

        # Fall back to normal intent routing.
        classify_started = time.perf_counter()
        intent = await self.router.classify(
            event.message_str,
            self._build_context(event),
        )
        classify_latency_ms = (time.perf_counter() - classify_started) * 1000.0
        event.set_extra("router_intent", asdict(intent))

        # Phase R0.1 / R0.2: 把分类决策落到 trace + jsonl，供后续 bench / dashboard 消费。
        await self._record_classify_observability(event, intent, classify_latency_ms)

        if intent.category == "task" and intent.workflow_kind:
            return await self._handle_task_intent(event, intent)

        if intent.category == "task" and intent.intent_type == "task_new":
            return await self._handle_task_new_intent(event, intent)

        # W1 / 2A-1: inline 处理群聊总结（没有对应 Star handler）
        if intent.category == "skill" and intent.skill_name == "group_summary":
            return await self._handle_group_summary(event, intent)

        if intent.category == "skill":
            return await self._handle_skill_intent(event, intent)

        return False

    def restore_event_message(self, event: AstrMessageEvent) -> None:
        original = event.get_extra("_router_original_message_str")
        if not original:
            return

        event.message_str = str(original)
        if hasattr(event.message_obj, "message_str"):
            event.message_obj.message_str = str(original)

        event.get_extra(default={}).pop("_router_original_message_str", None)
        event.get_extra(default={}).pop("_router_synthetic_message_str", None)

    def _build_context(self, event: AstrMessageEvent) -> dict[str, Any]:
        extras = event.get_extra(default={}) or {}
        return {
            "platform_id": event.get_platform_id(),
            "sender_id": event.get_sender_id(),
            "session_id": event.unified_msg_origin,
            "is_private_chat": event.is_private_chat(),
            "is_at_or_wake_command": event.is_at_or_wake_command,
            "activated_handler_count": len(extras.get("activated_handlers", []) or []),
            "session_key": extras.get("session_key"),
            "webhook_event": extras.get("webhook_event"),
        }

    async def _handle_task_new_intent(
        self, event: AstrMessageEvent, intent: Intent
    ) -> bool:
        lines = [
            "请指定 workflow 类型来创建任务，例如：",
            "• `/task intake marketing_plan <简述>` — 营销策划",
            "• `/task intake content_delivery <简述>` — 内容交付",
            "• `/task intake project_followup <简述>` — 项目跟进",
            "• `/task intake approval_request <简述>` — 审批确认",
        ]
        event.set_result(
            MessageEventResult().message("\n".join(lines)).use_t2i(False).stop_event(),
        )
        return True

    async def _handle_task_intent(
        self, event: AstrMessageEvent, intent: Intent
    ) -> bool:
        """Create a Harness task and let the normal AstrBot LLM answer first."""
        plugin_context = self.ctx.plugin_manager.context
        engine = plugin_context.harness_engine
        if engine is None or intent.workflow_kind is None:
            return False

        conversation_id = await self._get_or_create_current_conversation_id(event)
        task = await engine.create_task(
            create_workflow_request(
                workflow_kind=intent.workflow_kind,  # type: ignore[arg-type]
                brief=event.message_str.strip(),
                conversation_id=conversation_id,
                platform_id=event.get_platform_id(),
                session_id=event.unified_msg_origin,
                source="router_intent",
                message_text=event.message_str,
            ),
        )
        logger.info(
            "[RouterStage] Harness 任务已创建（#%s），交由 LLM 先行处理，"
            "如员工不满意将升级至 Hermes。",
            task.task_id[:8],
        )
        await self._maybe_attach_to_active_case(event, task)
        # Do not intercept the event; the normal AstrBot LLM should answer first.
        return False

    async def _maybe_attach_to_active_case(
        self,
        event: AstrMessageEvent,
        task: Any,
    ) -> None:
        """Soft-attach a freshly created Harness task to the session's active case.

        Disabled when ``case.auto_attach_task`` config is False, when no Case
        engine is wired (e.g. legacy installs), or when the session has no
        active case. Failures never propagate — Harness keeps working without
        Case linkage.
        """
        plugin_context = self.ctx.plugin_manager.context
        case_engine = getattr(plugin_context, "case_engine", None)
        if case_engine is None:
            return
        cfg = plugin_context.get_config() or {}
        case_cfg = cfg.get("case", {}) if isinstance(cfg, dict) else {}
        if case_cfg.get("auto_attach_task", True) is False:
            return
        try:
            case = await case_engine.get_current_case_for_session(
                event.unified_msg_origin,
            )
            if case is None:
                return
            await case_engine.attach_task(case.case_id, task.task_id)
            logger.info(
                "[RouterStage] task %s auto-attached to case %s",
                task.task_id[:8],
                case.case_id[:8],
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[RouterStage] case 自动挂接失败：%s", exc)

    async def _check_hermes_escalation(self, event: AstrMessageEvent) -> bool:
        """Escalate dissatisfied follow-up messages to Hermes when appropriate."""
        signal = self._satisfaction_detector.detect(event.message_str)
        if not signal.dissatisfied:
            return False

        # Explicit Hermes requests and high-confidence dissatisfaction can create a task.
        if signal.is_explicit_hermes_request or signal.confidence >= 0.88:
            task = await self._find_latest_active_task(event)
            return await self._handle_hermes_escalation(event, signal, task)

        # Medium-confidence dissatisfaction only escalates when a task is already active.
        if signal.confidence >= 0.65:
            task = await self._find_latest_active_task(event)
            if task is not None:
                return await self._handle_hermes_escalation(event, signal, task)

        return False

    async def _find_latest_active_task(self, event: AstrMessageEvent) -> Any:
        """Find the latest active Harness task, preferring grey-test topics."""
        plugin_context = self.ctx.plugin_manager.context
        engine = plugin_context.harness_engine
        if engine is None:
            return None
        try:
            tasks = await engine.store.list_tasks_for_session(
                event.unified_msg_origin,
                limit=10,
                statuses=("pending", "in_progress", "blocked", "review_required"),
            )
            for task in tasks:
                if (
                    hasattr(task, "payload")
                    and isinstance(task.payload, dict)
                    and task.payload.get("source") == "grey_topic"
                ):
                    return task
            return tasks[0] if tasks else None
        except Exception as exc:
            logger.debug("[RouterStage] 查询活跃任务失败：%s", exc)
            return None

    async def _handle_hermes_escalation(
        self,
        event: AstrMessageEvent,
        signal: SatisfactionSignal,
        task: Any = None,
    ) -> bool:
        """Dispatch an active or newly created task to Hermes for deep work."""
        plugin_context = self.ctx.plugin_manager.context
        engine = plugin_context.harness_engine

        if task is None and engine is not None:
            conversation_id = await self._get_or_create_current_conversation_id(event)
            task = await engine.create_task(
                create_workflow_request(
                    workflow_kind="project_followup",
                    brief=event.message_str.strip(),
                    conversation_id=conversation_id,
                    platform_id=event.get_platform_id(),
                    session_id=event.unified_msg_origin,
                    source="satisfaction_escalation",
                    message_text=event.message_str,
                )
            )

        if task is None:
            logger.warning("[RouterStage] Hermes 升级失败：无法获取或创建任务")
            return False

        # Mark as in_progress so the LLM response hook does not complete it.
        if engine is not None:
            try:
                await engine.mark_in_progress(task.task_id, note="dispatched_to_hermes")
            except Exception as exc:
                logger.debug(
                    "[RouterStage] mark_in_progress 失败（不阻断派发）：%s", exc
                )

        # Build a lightweight intent for the Hermes dispatch payload.
        workflow_kind = (
            task.payload.get("workflow_kind", "project_followup")
            if hasattr(task, "payload") and isinstance(task.payload, dict)
            else "project_followup"
        )
        intent = Intent(
            category="task",
            intent_type="hermes_escalation",
            confidence=signal.confidence,
            workflow_kind=workflow_kind,
        )

        await self._dispatch_to_hermes(task, intent, event)

        if (
            hasattr(task, "payload")
            and isinstance(task.payload, dict)
            and task.payload.get("source") == "grey_topic"
        ):
            reply_msg = (
                f"收到，已把当前灰度话题 #{task.task_id[:8]} 交给 Hermes 后台深挖，"
                "结果出来后会发回群里继续讨论。"
            )
        else:
            reply_msg = (
                "好的，已交给 Hermes 深度处理，完成后我会把结果发给你。"
                if signal.is_explicit_hermes_request
                else "收到，已安排 Hermes 对这个问题深入研究，结果出来后会通知你。"
            )
        event.set_result(
            MessageEventResult().message(reply_msg).use_t2i(False).stop_event()
        )

        logger.info(
            "[RouterStage] Hermes 升级成功：task=%s, session=%s, reason=%s, confidence=%.2f",
            task.task_id[:8],
            event.unified_msg_origin,
            signal.reason,
            signal.confidence,
        )
        return True

    async def _dispatch_to_hermes(
        self, task: Any, intent: Intent, event: AstrMessageEvent
    ) -> None:
        """将 Harness 任务异步派发给 Hermes 执行（方案 C）。"""
        cfg = self.ctx.plugin_manager.context.get_config()
        hcfg = cfg.get("hermes_bridge", {}) if cfg else {}
        task_webhook_url: str = hcfg.get(
            "task_webhook_url", "http://localhost:8644/webhooks/astrbot_task"
        )

        cognitive_context: dict[str, Any] = {}
        brief = event.message_str.strip()
        if hasattr(task, "payload") and isinstance(task.payload, dict):
            cognitive_context = task.payload.get("cognitive_context", {})
            if task.payload.get("source") == "grey_topic":
                brief = str(task.payload.get("brief") or task.title or brief)
                cognitive_context = dict(cognitive_context or {})
                cognitive_context["grey_topic"] = await self._build_grey_topic_context(
                    task,
                    event,
                )

        payload = {
            "task_id": task.task_id,
            "workflow_kind": intent.workflow_kind,
            "brief": brief,
            "session_id": event.unified_msg_origin,
            "unified_msg_origin": event.unified_msg_origin,
            "platform_id": event.get_platform_id(),
            "sender_id": event.get_sender_id(),
            "trigger_message": event.message_str,
            "cognitive_context": cognitive_context,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    task_webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Event": "harness_task",
                        "X-Task-ID": task.task_id,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status in (200, 201, 202):
                        logger.info(
                            "[RouterStage] 任务 %s 已派发给 Hermes（%s）",
                            task.task_id,
                            task_webhook_url,
                        )
                    else:
                        logger.warning(
                            "[RouterStage] Hermes 派发失败 HTTP %s: %s",
                            resp.status,
                            await resp.text(),
                        )
        except Exception as exc:
            logger.warning("[RouterStage] Hermes 派发异常（任务仍已创建）：%s", exc)

    async def _build_grey_topic_context(
        self,
        task: Any,
        event: AstrMessageEvent,
    ) -> dict[str, Any]:
        discussion: list[dict[str, Any]] = []
        try:
            events = await self.ctx.plugin_manager.context.harness_store.list_events(
                task.task_id,
            )
            discussion = [
                item.payload
                for item in events
                if item.event_type == "topic_discussion_message"
            ][-30:]
        except Exception as exc:
            logger.debug("[RouterStage] 读取灰度话题讨论失败：%s", exc)

        return {
            "topic_id": task.task_id,
            "title": getattr(task, "title", ""),
            "brief": task.payload.get("brief", "")
            if isinstance(task.payload, dict)
            else "",
            "status": getattr(task, "status", ""),
            "trigger_message": event.message_str,
            "discussion": discussion,
        }

    async def _handle_skill_intent(
        self,
        event: AstrMessageEvent,
        intent: Intent,
    ) -> bool:
        if not intent.skill_name:
            return False

        synthetic_command = intent.metadata.get("synthetic_command")
        if not synthetic_command:
            command_name = intent.metadata.get("command_name")
            if not command_name:
                return False
            synthetic_command = str(command_name)

        activated = await self._activate_skill_handlers(
            event,
            plugin_name=intent.skill_name,
            synthetic_message=str(synthetic_command),
        )
        if not activated and not event.get_extra("activated_handlers"):
            logger.debug(
                "Router skill '%s' has no registered star handlers, falling through to LLM.",
                intent.skill_name,
            )
        return activated

    async def _activate_skill_handlers(
        self,
        event: AstrMessageEvent,
        *,
        plugin_name: str,
        synthetic_message: str,
    ) -> bool:
        if self.ctx is None:
            return False

        original_message = event.message_str
        event.set_extra("_router_original_message_str", original_message)
        event.set_extra("_router_synthetic_message_str", synthetic_message)
        event.message_str = synthetic_message
        if hasattr(event.message_obj, "message_str"):
            event.message_obj.message_str = synthetic_message

        activated_handlers = []
        handlers_parsed_params: dict[str, dict[str, Any]] = {}
        for handler in star_handlers_registry.get_handlers_by_event_type(
            EventType.AdapterMessageEvent,
            plugins_name=event.plugins_name,
        ):
            plugin = star_map.get(handler.handler_module_path)
            if not plugin or plugin.name != plugin_name:
                continue

            passed = True
            permission_not_pass = False
            if len(handler.event_filters) == 0:
                continue

            for event_filter in handler.event_filters:
                try:
                    if isinstance(event_filter, PermissionTypeFilter):
                        if not event_filter.filter(event, self.ctx.astrbot_config):
                            permission_not_pass = True
                    elif not event_filter.filter(event, self.ctx.astrbot_config):
                        passed = False
                        break
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Router synthetic activation failed for %s: %s",
                        handler.handler_full_name,
                        exc,
                    )
                    passed = False
                    break

            if passed and not permission_not_pass:
                is_group_cmd_handler = any(
                    isinstance(event_filter, CommandGroupFilter)
                    for event_filter in handler.event_filters
                )
                if not is_group_cmd_handler:
                    activated_handlers.append(handler)
                    parsed = event.get_extra("parsed_params")
                    if parsed:
                        handlers_parsed_params[handler.handler_full_name] = parsed

            event.get_extra(default={}).pop("parsed_params", None)

        activated_handlers = await SessionPluginManager.filter_handlers_by_session(
            event,
            activated_handlers,
        )
        if not activated_handlers:
            self.restore_event_message(event)
            return False

        event.set_extra("activated_handlers", activated_handlers)
        event.set_extra("handlers_parsed_params", handlers_parsed_params)
        return False

    async def _handle_group_summary(
        self, event: AstrMessageEvent, intent: Intent
    ) -> bool:
        """W1 / 2A-1: 群聊总结。

        流程：找 provider + platform → parse_time_range → fetch_group_messages
              → summarize_group_chat → format_summary → 回群。
        任何关键失败都给用户明确文案（低打扰原则），不沉默。
        Case 软挂接：成功时把 summary 当作 deliverable 挂到当前活跃 case。
        """
        plugin_context = self.ctx.plugin_manager.context

        provider = plugin_context.get_using_provider(event.unified_msg_origin)
        if provider is None:
            event.set_result(
                MessageEventResult()
                .message("⚠️ 当前未配置 LLM provider，无法做群聊总结")
                .use_t2i(False)
                .stop_event()
            )
            return True

        # 找当前平台实例
        platform_inst = None
        target_id = event.get_platform_id()
        for inst in plugin_context.platform_manager.platform_insts:
            inst_id = ""
            try:
                inst_id = inst.meta().id
            except Exception:
                inst_id = ""
            if inst_id == target_id:
                platform_inst = inst
                break
        if platform_inst is None:
            event.set_result(
                MessageEventResult()
                .message(f"⚠️ 未找到平台实例 {target_id!r}，无法拉取群聊历史")
                .use_t2i(False)
                .stop_event()
            )
            return True

        # 解析时间范围 hint（从消息文本里抠）
        hint = (event.message_str or "").strip()
        time_range = parse_time_range(hint, now=datetime.now(timezone.utc))

        # 拉历史
        try:
            messages = await fetch_group_messages(
                platform_inst=platform_inst,
                message_history_manager=plugin_context.message_history_manager,
                event=event,
                time_range=time_range,
            )
        except UnsupportedPlatformError as exc:
            event.set_result(
                MessageEventResult()
                .message(f"⚠️ 当前平台暂不支持群聊总结：{exc}")
                .use_t2i(False)
                .stop_event()
            )
            return True

        if not messages:
            event.set_result(
                MessageEventResult()
                .message(f"⚠️ 在「{time_range.description}」窗口内没有可总结的群聊消息")
                .use_t2i(False)
                .stop_event()
            )
            return True

        # 调 LLM 总结
        summary = await summarize_group_chat(
            messages, llm_provider=provider, time_range=time_range
        )

        # 回群
        md = format_summary(summary)
        event.set_result(MessageEventResult().message(md).use_t2i(False).stop_event())

        # Case 软挂接（失败不阻断）
        try:
            case = await plugin_context.get_current_case(event.unified_msg_origin)
            if case and plugin_context.case_engine is not None:
                await plugin_context.case_engine.add_deliverable(
                    case.case_id,
                    kind="group_summary",
                    path=f"in-memory://summary-{datetime.now(timezone.utc).isoformat()}",
                    version=case.version,
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("[group_summary] Case soft-attach 跳过（不阻断）：%s", exc)

        logger.info(
            "[group_summary] 完成总结 umo=%s msg_count=%d range=%s",
            event.unified_msg_origin,
            summary.message_count,
            time_range.description,
        )
        return True

    async def _record_classify_observability(
        self,
        event: AstrMessageEvent,
        intent: Intent,
        latency_ms: float,
    ) -> None:
        """把 classify 结果同时写 trace span 与 jsonl 决策日志（Phase R0.1 / R0.2）。

        任何子步骤失败都不能阻断路由主流程。
        """
        matched_by = str(intent.metadata.get("matched_by") or "default")
        llm_called = matched_by == "llm"
        fallback_threshold = (
            float(getattr(self.router, "fallback_threshold", 0.75))
            if self.router is not None
            else 0.75
        )

        span_id: str | None = None
        try:
            event.trace.record(
                "router_classify",
                category=intent.category,
                intent_type=intent.intent_type,
                confidence=intent.confidence,
                workflow_kind=intent.workflow_kind,
                skill_name=intent.skill_name,
                matched_by=matched_by,
                llm_called=llm_called,
                fallback_threshold=fallback_threshold,
                latency_ms=round(latency_ms, 3),
            )
            span_id = getattr(event.trace, "span_id", None)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[RouterStage] trace.record 失败：%s", exc)

        if self.decision_logger is None:
            return
        try:
            record = build_decision_record(
                message=event.message_str or "",
                umo=event.unified_msg_origin,
                platform_id=event.get_platform_id(),
                category=intent.category,
                intent_type=intent.intent_type,
                confidence=intent.confidence,
                workflow_kind=intent.workflow_kind,
                skill_name=intent.skill_name,
                matched_by=matched_by,
                llm_called=llm_called,
                fallback_threshold=fallback_threshold,
                latency_ms=latency_ms,
                span_id=span_id,
            )
            await self.decision_logger.log(record)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[RouterStage] 决策日志写入失败：%s", exc)

    async def _classify_with_llm(
        self,
        system_prompt: str,
        prompt: str,
        context: dict[str, Any],
    ) -> str | None:
        if self.ctx is None:
            return None

        plugin_context = self.ctx.plugin_manager.context
        provider = plugin_context.get_using_provider(context.get("session_id"))
        if provider is None:
            return None

        try:
            response = await provider.text_chat(
                prompt=prompt,
                system_prompt=system_prompt,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Router LLM fallback failed: %s", exc)
            return None

        if response.completion_text:
            return response.completion_text
        return json.dumps(
            {
                "category": "conversation",
                "intent_type": "general",
                "confidence": 0.4,
            },
            ensure_ascii=False,
        )

    async def _get_or_create_current_conversation_id(
        self,
        event: AstrMessageEvent,
    ) -> str:
        conv_mgr = self.ctx.plugin_manager.context.conversation_manager
        umo = event.unified_msg_origin
        cid = await conv_mgr.get_curr_conversation_id(umo)
        if cid:
            return cid
        return await conv_mgr.new_conversation(umo, event.get_platform_id())
