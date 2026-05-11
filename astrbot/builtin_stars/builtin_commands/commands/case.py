from __future__ import annotations

from typing import TYPE_CHECKING, get_args

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.core.case import Case, CaseStatus

if TYPE_CHECKING:
    from astrbot.core.case import CaseEngine, CaseStore

VALID_STATUSES: tuple[str, ...] = tuple(get_args(CaseStatus))


class CaseCommands:
    """`/case` CLI for the Case aggregation layer (W0 Plan A 2A-0)."""

    def __init__(self, context: star.Context) -> None:
        self.context = context

    # --------------------------- helpers ---------------------------

    def _set_message(self, event: AstrMessageEvent, text: str) -> None:
        event.set_result(MessageEventResult().message(text).use_t2i(False))

    async def _ensure_engine_store(
        self,
        event: AstrMessageEvent,
    ) -> tuple[CaseEngine, CaseStore] | None:
        engine = self.context.case_engine
        store = self.context.case_store
        if engine is None or store is None:
            self._set_message(event, "Case 引擎未初始化。")
            return None
        return engine, store

    async def _resolve_active_case(
        self,
        event: AstrMessageEvent,
    ) -> Case | None:
        engine = self.context.case_engine
        if engine is None:
            self._set_message(event, "Case 引擎未初始化。")
            return None
        case = await engine.get_current_case_for_session(event.unified_msg_origin)
        if case is None:
            self._set_message(
                event,
                "当前会话没有活跃 case。用 `/case new <名称>` 新建一个。",
            )
        return case

    @staticmethod
    def _parse_new_args(arg_text: str) -> tuple[str, str | None]:
        """Parse ``<name> [--client <name>]``.

        Keeps it intentionally small — the command parser splits args on
        whitespace, so we re-join then look for the ``--client`` flag.
        """
        text = (arg_text or "").strip()
        if not text:
            return "", None
        if "--client" not in text:
            return text, None
        head, _, tail = text.partition("--client")
        return head.strip(), (tail.strip() or None)

    @staticmethod
    def _render_case_context(view: dict) -> str:
        lines = [
            f"**Case** {view['name']} (`{view['case_id'][:8]}`)",
            f"- status: {view['status']} | version: {view['version']}",
            f"- 甲方: {view.get('client_name') or '—'}",
            f"- session: {view['session_id']}",
            f"- 创建: {view['created_at']}",
            f"- 更新: {view['updated_at']}",
        ]
        roles = view.get("roles") or {}
        if roles:
            lines.append("- 角色:")
            for role, uid in roles.items():
                lines.append(f"  • {role}: {uid}")
        else:
            lines.append("- 角色: —")

        tasks = view.get("tasks") or []
        if tasks:
            lines.append(f"- 关联任务 ({len(tasks)}):")
            for task in tasks[:10]:
                if task.get("missing"):
                    lines.append(f"  • {task['task_id'][:8]} (已删除)")
                else:
                    lines.append(
                        f"  • {task['task_id'][:8]} | {task['status']} | {task['title']}",
                    )
            if len(tasks) > 10:
                lines.append(f"  ... 共 {len(tasks)} 条")
        else:
            lines.append("- 关联任务: —")

        deliverables = view.get("deliverables") or []
        if deliverables:
            lines.append(f"- 交付物 ({len(deliverables)}):")
            for d in deliverables[:10]:
                version = d.get("version")
                version_str = f" v{version}" if version is not None else ""
                lines.append(f"  • [{d.get('kind')}{version_str}] {d.get('path')}")
            if len(deliverables) > 10:
                lines.append(f"  ... 共 {len(deliverables)} 条")
        else:
            lines.append("- 交付物: —")
        return "\n".join(lines)

    # --------------------------- commands ---------------------------

    async def case_new(
        self,
        event: AstrMessageEvent,
        rest: str = "",
    ) -> None:
        name, client_name = self._parse_new_args(rest)
        if not name:
            self._set_message(
                event,
                "用法: /case new <名称> [--client <甲方>]",
            )
            return

        bundle = await self._ensure_engine_store(event)
        if bundle is None:
            return
        engine, _ = bundle

        case = await engine.create_case(
            name=name,
            platform_id=event.get_platform_id(),
            session_id=event.unified_msg_origin,
            client_name=client_name,
            payload={"source": "builtin_command"},
        )
        self._set_message(
            event,
            "已创建 Case：\n"
            f"- case_id: {case.case_id}\n"
            f"- name: {case.name}\n"
            f"- status: {case.status}\n"
            f"- 甲方: {case.client_name or '—'}",
        )

    async def case_context(self, event: AstrMessageEvent) -> None:
        case = await self._resolve_active_case(event)
        if case is None:
            return
        engine = self.context.case_engine
        view = await engine.get_case_context(case.case_id)
        if view is None:
            self._set_message(event, "未找到该 case。")
            return
        self._set_message(event, self._render_case_context(view))

    async def case_list(self, event: AstrMessageEvent) -> None:
        bundle = await self._ensure_engine_store(event)
        if bundle is None:
            return
        _, store = bundle
        cases = await store.list_cases_for_session(
            event.unified_msg_origin,
            limit=10,
        )
        if not cases:
            self._set_message(event, "当前会话还没有 case。")
            return
        lines = ["当前会话最近的 Case："]
        for case in cases:
            client = case.client_name or "—"
            lines.append(
                f"- {case.case_id[:8]} | {case.status} | {case.name}（甲方 {client}）",
            )
        self._set_message(event, "\n".join(lines))

    async def case_attach(
        self,
        event: AstrMessageEvent,
        task_id: str = "",
    ) -> None:
        if not task_id.strip():
            self._set_message(event, "用法: /case attach <task_id>")
            return

        case = await self._resolve_active_case(event)
        if case is None:
            return

        engine = self.context.case_engine
        try:
            updated = await engine.attach_task(case.case_id, task_id.strip())
        except LookupError:
            self._set_message(event, "Case 已不存在。")
            return
        self._set_message(
            event,
            f"已挂接 task {task_id.strip()[:8]} 到 case {updated.case_id[:8]}。"
            f"\n当前任务数: {len(updated.task_ids)}",
        )

    async def case_archive(self, event: AstrMessageEvent) -> None:
        case = await self._resolve_active_case(event)
        if case is None:
            return
        engine = self.context.case_engine
        archived = await engine.archive_case(case.case_id)
        self._set_message(
            event,
            f"Case 已归档：{archived.case_id[:8]} | {archived.name}",
        )

    async def case_status(
        self,
        event: AstrMessageEvent,
        status: str = "",
    ) -> None:
        normalized = (status or "").strip().lower()
        if normalized not in VALID_STATUSES:
            self._set_message(
                event,
                "用法: /case status <状态>。可选: " + ", ".join(VALID_STATUSES),
            )
            return

        case = await self._resolve_active_case(event)
        if case is None:
            return

        engine = self.context.case_engine
        updated = await engine.set_status(case.case_id, normalized)  # type: ignore[arg-type]
        self._set_message(
            event,
            f"Case 状态已更新：{updated.case_id[:8]} -> {updated.status}",
        )
