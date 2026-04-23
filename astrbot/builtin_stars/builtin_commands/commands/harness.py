from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.core.harness import (
    HarnessTaskCreateRequest,
    create_workflow_request,
    parse_workflow_result,
    validate_workflow_result,
)


class HarnessCommands:
    def __init__(self, context: star.Context) -> None:
        self.context = context

    async def _get_or_create_current_conversation_id(
        self,
        event: AstrMessageEvent,
    ) -> str:
        conv_mgr = self.context.conversation_manager
        umo = event.unified_msg_origin
        cid = await conv_mgr.get_curr_conversation_id(umo)
        if cid:
            return cid
        return await conv_mgr.new_conversation(umo, event.get_platform_id())

    async def _get_task_for_current_conversation(
        self,
        event: AstrMessageEvent,
        task_id: str,
    ):
        store = self.context.harness_store
        if store is None:
            event.set_result(
                MessageEventResult().message("Harness 存储未初始化。"),
            )
            return None

        task = await store.get_task(task_id.strip())
        if task is None:
            event.set_result(MessageEventResult().message("未找到该任务。"))
            return None

        conversation_id = await self._get_or_create_current_conversation_id(event)
        if task.conversation_id != conversation_id:
            event.set_result(
                MessageEventResult().message("该任务不属于当前会话，无法操作。"),
            )
            return None

        return task

    async def task_new(self, event: AstrMessageEvent, title: str = "") -> None:
        if not title.strip():
            event.set_result(
                MessageEventResult().message("请输入任务标题。用法: /task new 任务标题"),
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(
                MessageEventResult().message("Harness 引擎未初始化。"),
            )
            return

        conversation_id = await self._get_or_create_current_conversation_id(event)
        task = await engine.create_task(
            HarnessTaskCreateRequest(
                title=title.strip(),
                conversation_id=conversation_id,
                platform_id=event.get_platform_id(),
                session_id=event.unified_msg_origin,
                domain="general",
                payload={
                    "source": "builtin_command",
                    "message_text": event.message_str,
                },
            )
        )
        event.set_result(
            MessageEventResult().message(
                "已创建 Harness 任务：\n"
                f"- task_id: {task.task_id}\n"
                f"- title: {task.title}\n"
                f"- status: {task.status}\n"
                f"- conversation_id: {task.conversation_id}",
            ).use_t2i(False),
        )

    async def task_intake(
        self,
        event: AstrMessageEvent,
        workflow_kind: str = "",
        brief: str = "",
    ) -> None:
        if workflow_kind.strip() not in {
            "marketing_plan",
            "content_delivery",
            "project_followup",
            "approval_request",
        }:
            event.set_result(
                MessageEventResult().message(
                    "请输入有效工作流类型。可选: marketing_plan, content_delivery, "
                    "project_followup, approval_request",
                ),
            )
            return
        if not brief.strip():
            event.set_result(
                MessageEventResult().message(
                    "请输入任务简述。用法: /task intake workflow_kind 任务简述",
                ),
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(
                MessageEventResult().message("Harness 引擎未初始化。"),
            )
            return

        conversation_id = await self._get_or_create_current_conversation_id(event)
        task = await engine.create_task(
            create_workflow_request(
                workflow_kind=workflow_kind.strip(),  # type: ignore[arg-type]
                brief=brief.strip(),
                conversation_id=conversation_id,
                platform_id=event.get_platform_id(),
                session_id=event.unified_msg_origin,
                source="workflow_intake",
                message_text=event.message_str,
            )
        )
        await engine.complete_task(
            task.task_id,
            result={
                "summary": brief.strip()[:200],
                "source": "workflow_intake",
            },
        )
        lines = [
            "已创建 Workflow Harness 任务：",
            f"- task_id: {task.task_id}",
            f"- title: {task.title}",
            f"- domain: {task.domain}",
            f"- workflow_kind: {task.payload.get('workflow_kind')}",
        ]
        event.set_result(MessageEventResult().message("\n".join(lines)).use_t2i(False))

    async def task_ls(self, event: AstrMessageEvent) -> None:
        store = self.context.harness_store
        if store is None:
            event.set_result(
                MessageEventResult().message("Harness 存储未初始化。"),
            )
            return

        conversation_id = await self._get_or_create_current_conversation_id(event)
        tasks = await store.list_tasks_for_conversation(conversation_id, limit=10)
        if not tasks:
            event.set_result(
                MessageEventResult().message("当前会话还没有 Harness 任务。"),
            )
            return

        lines = ["当前会话 Harness 任务："]
        for task in tasks:
            lines.append(
                f"- {task.task_id} | {task.status} | {task.title}",
            )
        event.set_result(MessageEventResult().message("\n".join(lines)).use_t2i(False))

    async def task_show(self, event: AstrMessageEvent, task_id: str = "") -> None:
        if not task_id.strip():
            event.set_result(
                MessageEventResult().message("请输入 task_id。用法: /task show task_id"),
            )
            return

        store = self.context.harness_store
        if store is None:
            event.set_result(
                MessageEventResult().message("Harness 存储未初始化。"),
            )
            return

        task = await store.get_task(task_id.strip())
        if task is None:
            event.set_result(MessageEventResult().message("未找到该任务。"))
            return

        events = await store.list_events(task.task_id)
        reviews = await store.list_reviews(task.task_id)
        lines = [
            "Harness 任务详情：",
            f"- task_id: {task.task_id}",
            f"- title: {task.title}",
            f"- status: {task.status}",
            f"- domain: {task.domain}",
            f"- conversation_id: {task.conversation_id}",
            f"- events: {len(events)}",
            f"- reviews: {len(reviews)}",
        ]
        session_context = task.payload.get("session_context")
        if isinstance(session_context, dict):
            lines.extend(
                [
                    "- session_context:",
                    f"  lossless_items={session_context.get('total_items', 0)}",
                    f"  raw_messages={session_context.get('raw_message_items', 0)}",
                    f"  summary_leaves={session_context.get('summary_leaf_items', 0)}",
                    f"  last_ingested_seq={session_context.get('last_ingested_seq', 0)}",
                ]
            )
        cognitive_context = task.payload.get("cognitive_context")
        if isinstance(cognitive_context, dict):
            kb_names = cognitive_context.get("knowledge_base_names", [])
            recent_tasks = cognitive_context.get("recent_task_summaries", [])
            lines.extend(
                [
                    "- cognitive_context:",
                    f"  persona={cognitive_context.get('persona_name') or cognitive_context.get('persona_id') or 'none'}",
                    f"  knowledge_bases={', '.join(kb_names) if kb_names else 'none'}",
                    f"  recent_tasks={len(recent_tasks)}",
                ]
            )
        event.set_result(MessageEventResult().message("\n".join(lines)).use_t2i(False))

    async def task_start(
        self,
        event: AstrMessageEvent,
        task_id: str = "",
        note: str = "",
    ) -> None:
        if not task_id.strip():
            event.set_result(
                MessageEventResult().message(
                    "请输入 task_id。用法: /task start task_id [备注]",
                ),
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(
                MessageEventResult().message("Harness 引擎未初始化。"),
            )
            return

        task = await self._get_task_for_current_conversation(event, task_id)
        if task is None:
            return

        updated = await engine.mark_in_progress(task.task_id, note=note.strip() or None)
        event.set_result(
            MessageEventResult().message(
                f"任务已开始：{updated.task_id} | {updated.status} | {updated.title}",
            ).use_t2i(False),
        )

    async def task_review(
        self,
        event: AstrMessageEvent,
        task_id: str = "",
        reviewer_note: str = "",
    ) -> None:
        if not task_id.strip():
            event.set_result(
                MessageEventResult().message(
                    "请输入 task_id。用法: /task review task_id [审查备注]",
                ),
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(
                MessageEventResult().message("Harness 引擎未初始化。"),
            )
            return

        task = await self._get_task_for_current_conversation(event, task_id)
        if task is None:
            return

        updated = await engine.mark_review_required(
            task.task_id,
            reviewer_note=reviewer_note.strip() or None,
        )
        event.set_result(
            MessageEventResult().message(
                f"任务已进入审查：{updated.task_id} | {updated.status} | {updated.title}",
            ).use_t2i(False),
        )

    async def task_done(
        self,
        event: AstrMessageEvent,
        task_id: str = "",
        summary: str = "",
    ) -> None:
        if not task_id.strip():
            event.set_result(
                MessageEventResult().message(
                    "请输入 task_id。用法: /task done task_id [结果摘要]",
                ),
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(
                MessageEventResult().message("Harness 引擎未初始化。"),
            )
            return

        task = await self._get_task_for_current_conversation(event, task_id)
        if task is None:
            return

        result = parse_workflow_result(summary)
        validation = validate_workflow_result(task.payload, result)
        if validation is not None:
            result = {
                **result,
                "workflow_validation": {
                    "workflow_kind": validation.workflow_kind,
                    "missing_outputs": validation.missing_outputs,
                    "is_valid": validation.is_valid,
                },
            }
            await engine.append_trace(
                task.task_id,
                "workflow_result_validated",
                result["workflow_validation"],
            )

            if validation.review_required or validation.missing_outputs:
                note_parts = []
                if validation.review_required:
                    note_parts.append("workflow 默认需要审查")
                if validation.missing_outputs:
                    note_parts.append(
                        "缺少结果字段: " + ", ".join(validation.missing_outputs)
                    )
                updated = await engine.mark_review_required(
                    task.task_id,
                    reviewer_note="；".join(note_parts),
                    result=result,
                )
                event.set_result(
                    MessageEventResult().message(
                        f"任务结果已提交审查：{updated.task_id} | {updated.status} | {updated.title}"
                        + (
                            f"\n缺少字段: {', '.join(validation.missing_outputs)}"
                            if validation.missing_outputs
                            else ""
                        ),
                    ).use_t2i(False),
                )
                return

        updated = await engine.complete_task(task.task_id, result=result or None)
        event.set_result(
            MessageEventResult().message(
                f"任务已完成：{updated.task_id} | {updated.status} | {updated.title}",
            ).use_t2i(False),
        )

    async def task_fail(
        self,
        event: AstrMessageEvent,
        task_id: str = "",
        reason: str = "",
    ) -> None:
        if not task_id.strip():
            event.set_result(
                MessageEventResult().message(
                    "请输入 task_id。用法: /task fail task_id 失败原因",
                ),
            )
            return
        if not reason.strip():
            event.set_result(
                MessageEventResult().message("请输入失败原因。"),
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(
                MessageEventResult().message("Harness 引擎未初始化。"),
            )
            return

        task = await self._get_task_for_current_conversation(event, task_id)
        if task is None:
            return

        updated = await engine.fail_task(task.task_id, reason=reason.strip())
        event.set_result(
            MessageEventResult().message(
                f"任务已标记失败：{updated.task_id} | {updated.status} | {updated.title}",
            ).use_t2i(False),
        )

    async def task_approve(
        self,
        event: AstrMessageEvent,
        task_id: str = "",
        note: str = "",
    ) -> None:
        if not task_id.strip():
            event.set_result(
                MessageEventResult().message(
                    "请输入 task_id。用法: /task approve task_id [审批意见]",
                ),
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(MessageEventResult().message("Harness 引擎未初始化。"))
            return

        task = await self._get_task_for_current_conversation(event, task_id)
        if task is None:
            return

        review = await engine.approve_task(
            task.task_id,
            reviewer_id=event.get_sender_id() or event.unified_msg_origin,
            note=note.strip(),
        )
        event.set_result(
            MessageEventResult().message(
                f"任务已审批通过：{task.task_id} | reviewer={review.reviewer_id}",
            ).use_t2i(False),
        )

    async def task_reject(
        self,
        event: AstrMessageEvent,
        task_id: str = "",
        note: str = "",
    ) -> None:
        if not task_id.strip():
            event.set_result(
                MessageEventResult().message(
                    "请输入 task_id。用法: /task reject task_id 审批意见",
                ),
            )
            return
        if not note.strip():
            event.set_result(MessageEventResult().message("请输入驳回意见。"))
            return

        engine = self.context.harness_engine
        if engine is None:
            event.set_result(MessageEventResult().message("Harness 引擎未初始化。"))
            return

        task = await self._get_task_for_current_conversation(event, task_id)
        if task is None:
            return

        review = await engine.reject_task(
            task.task_id,
            reviewer_id=event.get_sender_id() or event.unified_msg_origin,
            note=note.strip(),
        )
        event.set_result(
            MessageEventResult().message(
                f"任务已驳回：{task.task_id} | reviewer={review.reviewer_id}",
            ).use_t2i(False),
        )
