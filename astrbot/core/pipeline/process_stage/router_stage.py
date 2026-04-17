from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from astrbot.core import logger
from astrbot.core.harness import create_workflow_request
from astrbot.core.message.message_event_result import MessageEventResult
from astrbot.core.pipeline.context import PipelineContext
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.router import Intent, IntentRouter
from astrbot.core.star.filter.command_group import CommandGroupFilter
from astrbot.core.star.filter.permission import PermissionTypeFilter
from astrbot.core.star.session_plugin_manager import SessionPluginManager
from astrbot.core.star.star import star_map
from astrbot.core.star.star_handler import EventType, star_handlers_registry


class RouterStage:
    def __init__(self) -> None:
        self.ctx: PipelineContext | None = None
        self.router: IntentRouter | None = None

    async def initialize(self, ctx: PipelineContext) -> None:
        self.ctx = ctx
        config_path = Path(__file__).resolve().parents[2] / "router_config.yaml"
        self.router = IntentRouter.from_yaml(
            config_path,
            llm_provider=self._classify_with_llm,
        )

    async def route(self, event: AstrMessageEvent) -> bool:
        if self.ctx is None or self.router is None:
            return False

        if event.get_extra("activated_handlers", []):
            return False

        intent = await self.router.classify(
            event.message_str,
            self._build_context(event),
        )
        event.set_extra("router_intent", asdict(intent))

        if intent.category == "task" and intent.workflow_kind:
            return await self._handle_task_intent(event, intent)

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

    async def _handle_task_intent(
        self, event: AstrMessageEvent, intent: Intent
    ) -> bool:
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
        lines = [
            "Router 已识别为任务请求，并创建了 Harness 任务：",
            f"- task_id: {task.task_id}",
            f"- title: {task.title}",
            f"- workflow_kind: {task.payload.get('workflow_kind')}",
            f"- confidence: {intent.confidence:.2f}",
        ]
        event.set_result(
            MessageEventResult().message("\n".join(lines)).use_t2i(False).stop_event(),
        )
        event.should_call_llm(True)
        return True

    async def _handle_skill_intent(
        self,
        event: AstrMessageEvent,
        intent: Intent,
    ) -> bool:
        if intent.skill_name != "dreamina_plugin":
            return False

        synthetic_command = intent.metadata.get("synthetic_command")
        if not synthetic_command:
            command_name = intent.metadata.get("command_name")
            if not command_name:
                return False
            synthetic_command = str(command_name)

        return await self._activate_skill_handlers(
            event,
            plugin_name="dreamina_plugin",
            synthetic_message=str(synthetic_command),
        )

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
