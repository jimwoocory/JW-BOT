from __future__ import annotations

from collections import Counter
from typing import Any

from harness_layer.config import DEFAULT_CONFIG
from harness_layer.knowledge_ingest import KnowledgeIngestService
from jw_claw.core_v2.async_tasks import AsyncJobStatus, AsyncTaskService
from jw_claw.core_v2.dashboard_api import DashboardAPIService
from jw_claw.core_v2.engine import HarnessEngine
from jw_claw.core_v2.inspection_replay import InspectionReplayService
from jw_claw.core_v2.memory_store import MemoryStore
from jw_claw.core_v2.memory_compressor import MemoryCompressor
from jw_claw.core_v2.memory_promotion import MemoryPromotionPolicy
from jw_claw.core_v2.notifications import NotificationCenter
from jw_claw.core_v2.operational_queries import OperationalQueryService
from jw_claw.core_v2.queryable_store import QueryableStore
from jw_claw.core_v2.replay import ReplayManager
from jw_claw.core_v2.short_term_memory import ShortTermMemoryManager
from jw_claw.core_v2.scheduled_tasks import ScheduleStatus, ScheduledTaskService
from jw_claw.core_v2.schemas.result import Result, ResultType
from jw_claw.core_v2.task_api import TaskAPIService
from .flags import (
    is_frontend_local_fallback_enabled,
    is_harness_debug_enabled,
    is_harness_enabled,
)


class HarnessAstrBotBridge:
    PROJECT_KEYWORDS = {
        "柳州五菱": ["五菱", "柳州五菱", "上汽通用五菱"],
        "柳汽东风": ["柳汽", "东风柳汽", "柳汽东风", "东风风行"],
        "新能源汽车": ["新能源汽车", "新能源", "电车", "混动", "纯电"],
        "平台热点": ["小红书", "抖音", "微博", "知乎", "视频号", "B站"],
        "营销策划": ["营销", "推广", "传播", "campaign", "文案", "策划", "公关", "KOL"],
    }
    PLATFORM_HINTS = ["小红书", "抖音", "微博", "知乎", "B站", "视频号"]
    COMPETITOR_HINTS = ["竞品", "对手", "友商", "品牌", "比亚迪", "特斯拉", "理想", "蔚来", "小鹏"]
    CREATIVE_HINTS = [
        "点子",
        "方向",
        "创意",
        "怎么做",
        "值不值得做",
        "值得做",
        "传播方向",
        "打法",
        "切入点",
        "值得关注",
        "关注点",
        "适不适合做",
        "能不能做",
    ]
    TRACKING_HINTS = [
        "每天",
        "每日",
        "持续",
        "持续关注",
        "长期",
        "长期关注",
        "跟踪",
        "追踪",
        "持续跟踪",
        "持续追踪",
        "盯着",
        "盯一下",
        "监控",
        "监测",
    ]
    NOISE_TOKENS = [
        "帮我",
        "请",
        "请帮我",
        "看一下",
        "看下",
        "查一下",
        "查下",
        "查查",
        "搜一下",
        "搜下",
        "搜搜",
        "分析一下",
        "分析",
        "整理一下",
        "整理",
        "做个",
        "来个",
        "盘点一下",
        "盘点",
        "汇总一下",
        "汇总",
        "总结一下",
        "总结",
        "做一份",
        "给我",
        "一个",
        "这波",
        "有啥",
        "有什么",
        "有没有",
        "今天",
        "当天",
        "这两天",
        "最近",
        "最新",
        "热度怎么样",
        "怎么样",
        "新动静",
        "消息",
        "一下",
        "关于",
        "的",
        "每天",
        "每日",
        "持续",
        "持续关注",
        "长期",
        "长期关注",
        "跟踪",
        "追踪",
        "持续跟踪",
        "持续追踪",
        "盯着",
        "盯一下",
        "监控",
        "监测",
    ]
    FILE_TYPE_OPTIONS = {
        "A": ("client_material", "客户资料"),
        "B": ("competitor_material", "竞品资料"),
        "C": ("platform_material", "平台资料"),
        "D": ("past_copywriting", "历史文案"),
        "E": ("project_plan", "项目方案"),
        "F": ("daily_weekly_report", "日报周报"),
        "G": ("data_report", "数据报表"),
        "H": ("other_material", "其他资料"),
        "Z": ("custom", "自定义类型"),
    }
    FILE_OWNER_OPTIONS = {
        "1": "柳州五菱",
        "2": "柳汽东风",
        "3": "比亚迪",
        "4": "小红书",
        "5": "抖音",
        "6": "其他",
        "9": "自定义归属",
    }

    def __init__(self, engine: HarnessEngine | None = None):
        self.engine = engine or HarnessEngine()
        self.knowledge_ingest = KnowledgeIngestService(DEFAULT_CONFIG)
        self.memory_store = MemoryStore()
        self.notification_center = NotificationCenter()
        self.async_task_service = AsyncTaskService(self.engine, notifications=self.notification_center)
        self.scheduled_task_service = ScheduledTaskService()
        self.short_term_memory = ShortTermMemoryManager()
        self.memory_compressor = MemoryCompressor(self.short_term_memory, self.memory_store)
        self.memory_promotion = MemoryPromotionPolicy(self.memory_store)
        self.query_service = OperationalQueryService(
            task_store=self.engine.task_store,
            memory_store=self.memory_store,
            project_keywords=self.PROJECT_KEYWORDS,
        )
        self.query_store = QueryableStore(
            task_store=self.engine.task_store,
            memory_store=self.memory_store,
        )
        self.replay_manager = ReplayManager(engine=self.engine)
        self.inspection_service = InspectionReplayService(
            replay_manager=self.replay_manager,
            query_store=self.query_store,
            async_tasks=self.async_task_service,
        )
        self.dashboard_service = DashboardAPIService(
            operational_queries=self.query_service,
            inspection_replay=self.inspection_service,
            async_tasks=self.async_task_service,
            schedules=self.scheduled_task_service,
            notifications=self.notification_center,
        )
        self.task_api = TaskAPIService(
            engine=self.engine,
            async_tasks=self.async_task_service,
            dashboard=self.dashboard_service,
        )
        self._file_ingest_sessions: dict[str, dict[str, Any]] = {}

    def set_llm_client(self, client) -> None:
        """Pass through an LLMClient to the engine's executor."""
        self.engine.set_llm_client(client)

    def start_file_ingest_from_path_text(self, file_path: str | None = None, event: Any = None) -> str:
        extracted_path, file_name = self._extract_uploaded_file(event)
        target_path = (file_path or extracted_path or "").strip()
        if not target_path:
            return (
                "【AstrBot📎】OC2 资料归档：\n"
                "• 未检测到可归档文件\n"
                "• 可直接上传文件，或使用: /oc2_file_upload /本地文件路径\n"
                "[OK]"
            )

        payload = self.knowledge_ingest.stage_file(
            target_path,
            source_name=file_name or target_path.split("/")[-1],
            uploader=self._session_key(event),
        )
        session_key = self._session_key(event)
        self._file_ingest_sessions[session_key] = {
            "upload_id": payload["upload_id"],
            "session_key": session_key,
            "step": "category",
            "source_name": payload.get("source_name", ""),
            "recommended_category": payload.get("recommended_category", ""),
            "brand_hint": payload.get("brand", "general"),
        }
        return self._build_file_category_prompt(payload)

    def start_file_ingest_from_text(self, source_name: str, content: str, event: Any = None) -> str:
        payload = self.knowledge_ingest.stage_text(
            content,
            source_name=source_name,
            uploader=self._session_key(event),
        )
        session_key = self._session_key(event)
        self._file_ingest_sessions[session_key] = {
            "upload_id": payload["upload_id"],
            "session_key": session_key,
            "step": "category",
            "source_name": payload.get("source_name", ""),
            "recommended_category": payload.get("recommended_category", ""),
            "brand_hint": payload.get("brand", "general"),
        }
        return self._build_file_category_prompt(payload)

    def reply_file_ingest_text(self, reply_text: str, event: Any = None) -> str:
        session = self._file_ingest_sessions.get(self._session_key(event))
        if not session:
            return (
                "【AstrBot📎】OC2 资料归档：\n"
                "• 当前没有待确认的资料\n"
                "• 先执行: /oc2_file_upload /本地文件路径\n"
                "[OK]"
            )

        reply = (reply_text or "").strip()
        if not reply:
            return (
                "【AstrBot📎】OC2 资料归档：\n"
                "• 请输入当前步骤的选择或内容\n"
                "[OK]"
            )

        step = session.get("step", "category")
        if step == "category":
            return self._reply_file_category(session, reply)
        if step == "custom_category":
            return self._reply_file_custom_category(session, reply)
        if step == "owner":
            return self._reply_file_owner(session, reply)
        if step == "custom_owner":
            return self._reply_file_custom_owner(session, reply)
        if step == "note":
            return self._reply_file_note(session, reply)
        return "【AstrBot📎】OC2 资料归档：\n• 当前会话状态异常\n[OK]"

    def get_file_pending_text(self) -> str:
        items = self.knowledge_ingest.list_pending()
        lines = ["【AstrBot📂】OC2 待归档资料："]
        if not items:
            lines.append("• 当前没有待确认资料")
            lines.append("[OK]")
            return "\n".join(lines)

        for item in items[:10]:
            lines.append(
                f"• {item.get('upload_id', '')} | {item.get('source_name', '')} | 推荐: {item.get('recommended_category', '')} | 归属提示: {item.get('brand', 'general')}"
            )
        lines.append("[OK]")
        return "\n".join(lines)

    def get_file_search_text(self, query: str, limit: int = 10) -> str:
        keyword = (query or "").strip()
        lines = [f"【AstrBot📂】OC2 资料检索：{keyword or '全部'}"]
        memories = self.memory_store.list_memories(limit=max(limit * 5, 50), source="file_ingest_auto")
        rows = []
        for memory in memories:
            meta = memory.metadata or {}
            searchable = " ".join(
                [
                    meta.get("source_name", ""),
                    meta.get("category_label", ""),
                    meta.get("category", ""),
                    meta.get("brand", ""),
                    meta.get("note", ""),
                    meta.get("final_path", ""),
                    memory.content,
                ]
            ).lower()
            if keyword and keyword.lower() not in searchable:
                continue
            rows.append(
                {
                    "source_name": meta.get("source_name", ""),
                    "category_label": meta.get("category_label") or meta.get("category", ""),
                    "brand": meta.get("brand", "general"),
                    "note": meta.get("note", ""),
                }
            )
        rows = rows[:limit]
        if not rows:
            lines.append("• 未找到匹配资料")
            lines.append("• 先执行: /oc2_file_upload /本地文件路径")
            lines.append("[OK]")
            return "\n".join(lines)

        lines.append("资料列表")
        for row in rows:
            line = f"• {row['source_name']} | 类型: {row['category_label']} | 归属: {row['brand']}"
            if row["note"]:
                line += f" | 备注: {row['note']}"
            lines.append(line)
        lines.append("建议入口")
        lines.append("• 继续归档: /oc2_file_upload /本地文件路径")
        if keyword:
            lines.append(f"• 深挖项目: /oc2_project_context {keyword}")
        lines.append("[OK]")
        return "\n".join(lines)

    async def handle_command(
        self,
        command_name: str,
        prompt: str | None = None,
        event: Any = None,
    ) -> Result:
        raw_event = self._build_raw_event(command_name, prompt, event)
        submission = await self.task_api.submit_sync(raw_event)
        result = submission.result
        self._capture_short_term_memory(command_name, prompt, result)
        self._capture_task_memory(result)
        return result

    async def handle_command_text(
        self,
        command_name: str,
        prompt: str | None = None,
        event: Any = None,
    ) -> str:
        result = await self.handle_command(command_name, prompt=prompt, event=event)
        return self._result_to_text(result)

    async def get_daily_brief_text(
        self,
        query: str,
        event: Any = None,
    ) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 每日简报：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        news_result = await self.handle_command("mtoc_news", query, event=event)
        hot_result = await self.handle_command("mtoc_hot", query, event=event)
        news_text = self._result_to_text(news_result)
        hot_text = self._result_to_text(hot_result)
        context_text = self.get_project_dashboard_text(limit=5, query=query)

        lines = [
            "【AstrBot📰】OC2 每日简报：",
            f"• 主题: {query}",
            "数据来源",
            f"• 新闻: {self._build_brief_source_label(news_result)}",
            f"• 热点: {self._build_brief_source_label(hot_result)}",
            "实时数据摘要",
            "今日新闻",
        ]
        lines.extend(self._compact_text_block(news_text, max_lines=5))
        lines.append("今日热点")
        lines.extend(self._compact_text_block(hot_text, max_lines=5))
        lines.append("客户上下文")
        lines.extend(self._compact_text_block(context_text, max_lines=6))
        lines.append("建议下一步")
        lines.append(f"• 继续查看: /oc2_project_context {query}")
        lines.append(f"• 深挖记忆: /oc2_memory_search {query}")
        lines.append("[OK]")
        text = "\n".join(lines)
        self._store_brief_memory("daily", query, text)
        return text

    async def get_competitor_brief_text(
        self,
        brand: str,
        event: Any = None,
    ) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 竞品简报：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        competitor_result = await self.handle_command("mtoc_competitor", brand, event=event)
        news_result = await self.handle_command("mtoc_news", brand, event=event)
        competitor_text = self._result_to_text(competitor_result)
        news_text = self._result_to_text(news_result)
        context_text = self.get_project_dashboard_text(limit=5, query=brand)

        lines = [
            "【AstrBot📌】OC2 竞品简报：",
            f"• 品牌: {brand}",
            "数据来源",
            f"• 竞品: {self._build_brief_source_label(competitor_result)}",
            f"• 动态: {self._build_brief_source_label(news_result)}",
            "实时数据摘要",
            "竞品速览",
        ]
        lines.extend(self._compact_text_block(competitor_text, max_lines=5))
        lines.append("最新动态")
        lines.extend(self._compact_text_block(news_text, max_lines=5))
        lines.append("客户上下文")
        lines.extend(self._compact_text_block(context_text, max_lines=6))
        lines.append("建议下一步")
        lines.append(f"• 深挖竞品: /mtoc_competitor {brand}")
        lines.append(f"• 查看项目: /oc2_project_context {brand}")
        lines.append("[OK]")
        text = "\n".join(lines)
        self._store_brief_memory("competitor", brand, text)
        return text

    async def get_platform_brief_text(
        self,
        topic: str,
        event: Any = None,
    ) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 平台热点简报：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        hot_result = await self.handle_command("mtoc_hot", topic, event=event)
        news_result = await self.handle_command("mtoc_news", topic, event=event)
        hot_text = self._result_to_text(hot_result)
        news_text = self._result_to_text(news_result)
        memory_text = self.search_memory_text(topic, limit=5)

        lines = [
            "【AstrBot📣】OC2 平台热点简报：",
            f"• 主题: {topic}",
            "数据来源",
            f"• 热点: {self._build_brief_source_label(hot_result)}",
            f"• 动态: {self._build_brief_source_label(news_result)}",
            "实时数据摘要",
            "平台热点",
        ]
        lines.extend(self._compact_text_block(hot_text, max_lines=5))
        lines.append("平台动态")
        lines.extend(self._compact_text_block(news_text, max_lines=5))
        lines.append("历史线索")
        lines.extend(self._compact_text_block(memory_text, max_lines=6))
        lines.append("建议下一步")
        lines.append(f"• 深挖热点: /mtoc_hot {topic}")
        lines.append(f"• 搜索线索: /oc2_memory_search {topic}")
        lines.append("[OK]")
        text = "\n".join(lines)
        self._store_brief_memory("platform", topic, text)
        return text

    async def get_request_text(
        self,
        request_text: str,
        event: Any = None,
    ) -> str:
        explicit_command_hint = self._build_explicit_command_hint(request_text)
        if explicit_command_hint:
            return explicit_command_hint
        command_name, prompt, label, interval_minutes = self._infer_request_command(request_text)
        result_use = self._detect_request_use(request_text, interval_minutes)
        if interval_minutes is not None:
            kind_map = {
                "oc2_daily_brief": "daily",
                "oc2_competitor_brief": "competitor",
                "oc2_platform_brief": "platform",
            }
            workflow_kind = kind_map.get(command_name, "daily")
            result_text = self.create_brief_schedule_text(
                workflow_kind,
                prompt,
                interval_minutes=interval_minutes,
            )
            execution_text = f"每日订阅（每 {interval_minutes} 分钟执行一次）"
            command_text = f"/oc2_brief_schedule {workflow_kind} {prompt} {interval_minutes}"
        elif command_name == "oc2_competitor_brief":
            result_text = await self.get_competitor_brief_text(prompt, event=event)
            execution_text = "即时简报"
            command_text = f"/{command_name} {prompt}"
        elif command_name == "oc2_platform_brief":
            result_text = await self.get_platform_brief_text(prompt, event=event)
            execution_text = "即时简报"
            command_text = f"/{command_name} {prompt}"
        else:
            result_text = await self.get_daily_brief_text(prompt, event=event)
            execution_text = "即时简报"
            command_text = f"/{command_name} {prompt}"

        self._store_request_memory(
            request_text=request_text,
            workflow_label=label,
            prompt=prompt,
            execution_text=execution_text,
            command_text=command_text,
            result_use=result_use,
        )

        lines = [
            "【AstrBot🎯】OC2 需求识别：",
            f"• 原始需求: {request_text}",
            f"• 已识别: {label}",
            f"• 工作流: {label}",
            f"• 主题: {prompt}",
            f"• 执行方式: {execution_text}",
            f"• 结果用途: {result_use}",
            f"• 转换命令: {command_text}" if interval_minutes is None else f"• 转换订阅: {command_text}",
            "[OK]",
            "",
            result_text,
        ]
        return "\n".join(lines)

    @staticmethod
    def _build_explicit_command_hint(text: str) -> str | None:
        stripped = (text or "").strip()
        if not stripped:
            return None
        lines = [line.strip() for line in stripped.splitlines() if line.strip()]
        slash_lines = [line for line in lines if line.startswith("/")]
        if not slash_lines:
            return None

        if len(lines) == 1:
            command_preview = slash_lines[0]
            return "\n".join(
                [
                    "【AstrBot⚠️】OC2 请求入口提示：",
                    "• 当前内容已是显式命令",
                    "• 请直接发送这条命令，不要再走 /oc2_request 识别入口",
                    f"• 命令: {command_preview}",
                    "[OK]",
                ]
            )

        preview = slash_lines[:4]
        lines_out = [
            "【AstrBot⚠️】OC2 请求入口提示：",
            "• 检测到命令序列输入",
            "• 请将以下命令逐条单独发送，不要一次发送多行",
        ]
        lines_out.extend(f"• {line}" for line in preview)
        if len(slash_lines) > len(preview):
            lines_out.append(f"• 其余 {len(slash_lines) - len(preview)} 条命令也请逐条发送")
        lines_out.append("[OK]")
        return "\n".join(lines_out)

    async def submit_async_command(
        self,
        command_name: str,
        prompt: str | None = None,
        event: Any = None,
    ):
        raw_event = self._build_raw_event(command_name, prompt, event)
        submission = await self.task_api.submit_async(
            raw_event,
            metadata={
                "command_name": command_name,
                "prompt": prompt or "",
                "source": "astrbot_bridge",
            },
        )
        return self.async_task_service.get_job(submission.job_id)

    async def submit_async_command_text(
        self,
        command_name: str,
        prompt: str | None = None,
        event: Any = None,
    ) -> str:
        job = await self.submit_async_command(command_name, prompt=prompt, event=event)
        return (
            "【AstrBot⏳】OC2 异步任务提交：\n"
            f"• Job ID: {job.job_id}\n"
            f"• 状态: {job.status.value}\n"
            f"• 命令: /{command_name} {prompt or ''}".rstrip()
            + "\n[OK]"
        )

    async def retry_async_job_text(self, job_id: str) -> str:
        job = self.async_task_service.retry_job(job_id)
        await self.async_task_service.start_worker()
        return f"【AstrBot🔁】OC2 异步任务重试：\n• Job ID: {job.job_id}\n• 状态: {job.status.value}\n[OK]"

    async def resume_async_job_text(self, job_id: str) -> str:
        job = self.async_task_service.resume_job(job_id)
        await self.async_task_service.start_worker()
        return f"【AstrBot🔁】OC2 异步任务恢复：\n• Job ID: {job.job_id}\n• 状态: {job.status.value}\n[OK]"

    def get_engine_status_text(self) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 状态检查：\nJW-Claw Harness\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"
        status = self.engine.get_status()
        async_summary = self.dashboard_service.get_overview_snapshot(task_limit=5, memory_limit=5).async_summary
        sc = async_summary.status_counts
        failed = sc.get("failed", 0)
        running = sc.get("running", 0)
        queued = sc.get("queued", 0)
        completed = sc.get("completed", 0)
        health = "ONLINE ✅" if failed == 0 else "ONLINE ⚠️"
        debug_status = "开启" if is_harness_debug_enabled() else "关闭"
        advice = "/oc2_async_tasks" if failed > 0 else "/oc2_tasks"
        lines = [
            "【AstrBot🟢】OC2 状态检查：",
            "JW-Claw Harness",
            f"• 状态: {health}",
            f"• 版本: {status['engine_version']}",
            f"• 调试: {debug_status}",
            f"• 前端本地兜底: {'开启' if is_frontend_local_fallback_enabled() else '关闭'}",
            f"• 路由规则数: {status['router_rules_count']}",
            f"• 规则域: {', '.join(status['domains_planned'])}",
            f"• 已注册工具: {', '.join(status['tools_registered'])}",
            f"• 审查器: {', '.join(status['reviewers'])}",
            "任务概况",
            f"• 总任务数: {status['tasks_total']}",
            f"• 活动任务: {status['tasks_active']}",
            f"• 异步任务: queued:{queued}, running:{running}, completed:{completed}, failed:{failed}",
            "建议入口",
            f"• 优先查看: {advice}",
            "• 执行记录: /oc2_inspection",
            "• 记忆总览: /oc2_memory",
            "[OK]",
        ]
        return "\n".join(lines)

    def get_route_debug_text(self, message_text: str) -> str:
        if not is_harness_enabled() or not is_harness_debug_enabled():
            return "【AstrBot⚠️】OC2 路由调试：\n• 调试当前未启用\n[OK]"
        debug_info = self.engine.get_route_debug({"content": message_text})
        route = debug_info["route"]
        command_extract = debug_info["command_extract"]

        lines = ["【AstrBot🧭】OC2 路由调试："]
        lines.append(f"• 输入: {debug_info['message']['content']}")
        lines.append(f"• 是否命令: {'是' if debug_info['is_command'] else '否'}")
        lines.append(f"• 动作: {route['action']}")
        lines.append(f"• 域: {route['domain']}")
        lines.append(f"• 目标: {route['target'] or '无'}")
        lines.append(f"• 置信度: {route['confidence']}")
        if command_extract:
            lines.append(f"• 命令解析: {command_extract[0]} | 参数: {command_extract[1] or ''}")
        if route.get("metadata"):
            lines.append(f"• 元数据: {route['metadata']}")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_inspection_overview_text(self, task_limit: int = 10) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 详细检查：\nJW-Claw Inspection\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        snapshot = self.dashboard_service.get_overview_snapshot(task_limit=task_limit, memory_limit=task_limit)
        inspection = snapshot.inspection_overview
        lines = ["【AstrBot🟢】OC2 详细检查：", "JW-Claw Inspection"]
        lines.append(f"• Replay 用例总数: {inspection.replay_total_cases}")
        if inspection.replay_domain_counts:
            replay_text = ", ".join(f"{domain}:{count}" for domain, count in inspection.replay_domain_counts.items())
            lines.append(f"• Replay 域覆盖: {replay_text}")
        lines.append("近期任务")
        lines.append(f"• 最近任务数: {inspection.recent_task_total}")
        if inspection.recent_task_status_counts:
            task_text = ", ".join(f"{status}:{count}" for status, count in inspection.recent_task_status_counts.items())
            lines.append(f"• 任务状态: {task_text}")
        lines.append("异步任务")
        lines.append(f"• 最近异步任务数: {inspection.recent_async_total}")
        if inspection.recent_async_status_counts:
            async_text = ", ".join(f"{status}:{count}" for status, count in inspection.recent_async_status_counts.items())
            lines.append(f"• 异步状态: {async_text}")
        if inspection.recent_async_failure_counts:
            failure_text = ", ".join(f"{kind}:{count}" for kind, count in inspection.recent_async_failure_counts.items())
            lines.append(f"• 异步失败分类: {failure_text}")
        if inspection.recent_async_history:
            lines.append("最近异步历史")
            for entry in inspection.recent_async_history[:5]:
                line = f"• {entry['job_id']} | {entry['to_status']}"
                if entry.get("from_status"):
                    line = f"• {entry['job_id']} | {entry['from_status']} -> {entry['to_status']}"
                if entry.get("reason"):
                    line += f" | {entry['reason']}"
                if entry.get("error"):
                    line += f" | error={entry['error']}"
                lines.append(line)
        lines.append("建议入口")
        lines.append("• 异步列表: /oc2_async_tasks")
        lines.append("• 异步详情: /oc2_async_detail <job_id>")
        lines.append("• 任务列表: /oc2_tasks")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_schedule_summary_text(self, limit: int = 10) -> str:
        snapshot = self.dashboard_service.get_schedule_summary_snapshot(limit=limit)
        lines = ["【AstrBot🗓️】OC2 计划任务："]
        if snapshot.status_counts:
            status_text = ", ".join(f"{k}:{v}" for k, v in snapshot.status_counts.items())
            lines.append(f"• 状态统计: {status_text}")
        if not snapshot.items:
            lines.append("• 暂无计划任务")
            lines.append("[OK]")
            return "\n".join(lines)
        lines.append("任务列表")
        for item in snapshot.items:
            lines.append(
                f"• {item.schedule_id} | {item.status} | /{item.command_name} {item.prompt}".rstrip()
                + f" | every={item.interval_minutes}m | runs={item.run_count}"
            )
        lines.append("[OK]")
        return "\n".join(lines)

    def get_notification_summary_text(self, limit: int = 10) -> str:
        snapshot = self.dashboard_service.get_notification_summary_snapshot(limit=limit)
        lines = ["【AstrBot🔔】OC2 通知回执："]
        if not snapshot.items:
            lines.append("• 暂无通知回执")
            lines.append("[OK]")
            return "\n".join(lines)
        lines.append("最近通知")
        for item in snapshot.items:
            lines.append(f"• {item.kind} | {item.title}")
            if item.body:
                lines.append(f"  • {item.body[:120]}")
        lines.append("[OK]")
        return "\n".join(lines)

    def create_schedule_text(self, command_name: str, prompt: str = "", interval_minutes: int = 60) -> str:
        item = self.scheduled_task_service.create_schedule(
            command_name=command_name,
            prompt=prompt,
            interval_minutes=interval_minutes,
            metadata={"source": "astrbot_bridge"},
        )
        return (
            "【AstrBot🗓️】OC2 计划任务创建：\n"
            f"• Schedule ID: {item.schedule_id}\n"
            f"• 命令: /{item.command_name} {item.prompt}\n"
            f"• 间隔: {item.interval_minutes} 分钟\n"
            f"• 状态: {item.status.value}\n"
            "[OK]"
        )

    def create_brief_schedule_text(self, kind: str, topic: str, interval_minutes: int = 1440) -> str:
        command_map = {
            "daily": "oc2_daily_brief",
            "competitor": "oc2_competitor_brief",
            "platform": "oc2_platform_brief",
        }
        command_name = command_map.get(kind)
        if not command_name:
            return "【AstrBot⚠️】OC2 简报订阅：\n• 类型无效\n• 可用值: daily, competitor, platform\n[OK]"
        item = self.scheduled_task_service.create_schedule(
            command_name=command_name,
            prompt=topic,
            interval_minutes=interval_minutes,
            metadata={
                "source": "brief_schedule",
                "brief_kind": kind,
            },
        )
        return (
            "【AstrBot🗓️】OC2 简报订阅：\n"
            f"• Schedule ID: {item.schedule_id}\n"
            f"• 类型: {kind}\n"
            f"• 命令: /{item.command_name} {item.prompt}\n"
            f"• 间隔: {item.interval_minutes} 分钟\n"
            f"• 状态: {item.status.value}\n"
            "[OK]"
        )

    def get_async_job_summary_text(self, limit: int = 10, status: str | None = None) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 异步任务：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        status_enum = None
        if status:
            try:
                status_enum = AsyncJobStatus(status.strip().lower())
            except ValueError:
                return "【AstrBot⚠️】OC2 异步任务：\n• 状态过滤无效\n• 可用值: queued, running, completed, failed, cancelled\n[OK]"

        snapshot = self.dashboard_service.get_async_job_summary_snapshot(limit=limit, status=status_enum)
        lines = ["【AstrBot📋】OC2 异步任务："]
        status_text = ", ".join(f"{label}:{count}" for label, count in snapshot.status_counts.items())
        lines.append(f"• 状态统计: {status_text or 'queued:0, running:0, completed:0, failed:0'}")
        if not snapshot.items:
            lines.append("• 暂无异步任务")
            lines.append(f"• 推荐下一步: {snapshot.next_step_hint}")
            lines.append("[OK]")
            return "\n".join(lines)

        lines.append("任务列表")
        for item in snapshot.items:
            line = f"• {item.job_id} | {item.status} | attempts={item.attempts}"
            if item.task_id:
                line += f" | task={item.task_id}"
            if item.result_type:
                line += f" | result={item.result_type}"
            if item.task_status:
                line += f" | task_status={item.task_status}"
            if item.total_steps:
                line += f" | progress={item.completed_steps}/{item.total_steps}"
            lines.append(line)
            if item.current_step:
                lines.append(f"  • 当前步骤: {item.current_step}")
            if item.error:
                lines.append(f"  • 错误: {item.error}")
                if item.failure_kind:
                    lines.append(f"  • 失败分类: {item.failure_kind}")
                if item.suggested_action:
                    lines.append(f"  • 建议: {item.suggested_action}")
            elif item.result_preview:
                lines.append(f"  • 结果: {item.result_preview[:100]}")
        lines.append(f"• 推荐下一步: {snapshot.next_step_hint}")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_async_job_detail_text(self, job_id: str) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 异步任务详情：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        snapshot = self.dashboard_service.get_async_job_detail_snapshot(job_id)
        lines = ["【AstrBot🔍】OC2 异步任务详情："]
        if not snapshot.job:
            lines.append("• 未找到对应异步任务")
            lines.append(f"• 推荐下一步: {snapshot.next_step_hint}")
            lines.append("[OK]")
            return "\n".join(lines)

        item = snapshot.job
        lines.append(f"• 状态: {item.status}")
        lines.append(f"• 尝试次数: {item.attempts}")
        lines.append(f"• Job ID: {item.job_id}")
        if item.task_id:
            lines.append(f"• Task ID: {item.task_id}")
        if item.result_type:
            lines.append(f"• 结果类型: {item.result_type}")
        if item.task_status:
            lines.append(f"• 任务状态: {item.task_status}")
        if item.total_steps:
            lines.append(f"• 执行进度: {item.completed_steps}/{item.total_steps}")
        if item.current_step:
            lines.append(f"• 当前步骤: {item.current_step}")
        if item.error:
            lines.append(f"• 错误: {item.error}")
            if item.failure_kind:
                lines.append(f"• 失败分类: {item.failure_kind}")
        elif item.result_preview:
            lines.append(f"• 结果预览: {item.result_preview}")
        if item.suggested_action:
            lines.append(f"• 建议动作: {item.suggested_action}")
        if snapshot.metadata:
            lines.append("元数据")
            for key, value in sorted(snapshot.metadata.items()):
                lines.append(f"• {key}: {value}")
        if snapshot.history:
            lines.append("状态历史")
            for entry in snapshot.history:
                line = f"• {entry['to_status']}"
                if entry.get("from_status"):
                    line = f"• {entry['from_status']} -> {entry['to_status']}"
                if entry.get("reason"):
                    line += f" | {entry['reason']}"
                if entry.get("error"):
                    line += f" | error={entry['error']}"
                lines.append(line)
        lines.append(f"• 原始请求: {snapshot.raw_event_preview}")
        lines.append(f"• 推荐下一步: {snapshot.next_step_hint}")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_task_summary_text(self, limit: int = 10) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 任务列表：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"
        snapshot = self.dashboard_service.get_workspace_snapshot(task_limit=limit, memory_limit=limit).task_summary

        lines = ["【AstrBot📋】OC2 任务列表："]
        if not snapshot.items:
            lines.append("• 暂无任务")
            lines.append("[OK]")
            return "\n".join(lines)

        if snapshot.category_counts:
            category_text = ", ".join(
                f"{category}({count})"
                for category, count in Counter(snapshot.category_counts).most_common()
            )
            lines.append(f"• 任务分类: {category_text}")

        if snapshot.priority_lines:
            lines.append("优先关注")
            for line in snapshot.priority_lines:
                lines.append(f"• {line}")

        lines.append("任务明细")
        for item in snapshot.items:
            lines.append(
                f"• {item.task_id} | {item.status} | {item.domain} | {item.category} | {item.execution_mode} | {item.intent[:60]}"
            )
        lines.append(f"• 推荐下一步: {snapshot.next_step_hint}")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_context_memory_text(self, limit: int = 10, query: str | None = None) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 上下文记忆：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        snapshot = self.dashboard_service.get_workspace_snapshot(
            query=query,
            task_limit=limit,
            memory_limit=limit,
        ).context_memory
        lines = ["【AstrBot🧠】OC2 上下文记忆："]
        if not snapshot.items:
            lines.append("• 暂无可用上下文")
            lines.append("[OK]")
            return "\n".join(lines)

        if query:
            lines.append(f"• 搜索: {query}")
        lines.append("上下文列表")
        for index, item in enumerate(snapshot.items, 1):
            task_line = (
                f"• {index}. [{item.domain}/{item.status}] "
                f"{item.intent[:80]}"
            )
            lines.append(task_line)
            if item.followup:
                lines.append(f"  • 跟进: {item.followup}")
            if item.error:
                lines.append(f"  • 错误: {item.error}")
            elif item.latest_log:
                lines.append(f"  • 最近日志: {item.latest_log}")
        lines.append(f"• 推荐深挖: {snapshot.deep_dive_hint}")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_project_dashboard_text(self, limit: int = 10, query: str | None = None) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 客户项目上下文：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        snapshot = self.dashboard_service.get_workspace_snapshot(
            query=query,
            task_limit=limit,
            memory_limit=limit,
        ).project_dashboard
        title = "【AstrBot📁】OC2 客户项目上下文："
        if query:
            title = f"【AstrBot📁】OC2 客户项目上下文 - {query}："
        lines = [title]
        if not (snapshot.matched_labels or snapshot.recent_tasks or snapshot.highlight_memories):
            lines.append("• 暂无客户项目上下文")
            lines.append("[OK]")
            return "\n".join(lines)

        if snapshot.matched_labels:
            lines.append("项目概况")
            lines.append("• 识别主题: " + " / ".join(snapshot.matched_labels))
        else:
            lines.append("项目概况")
            lines.append("• 识别主题: 通用推广项目")

        if snapshot.label_counts:
            top_labels = ", ".join(
                f"{label}({count})"
                for label, count in Counter(snapshot.label_counts).most_common(5)
            )
            lines.append(f"• 主题热度: {top_labels}")

        if snapshot.domain_counts:
            domain_text = ", ".join(
                f"{domain}:{count}" for domain, count in snapshot.domain_counts.items()
            )
            lines.append(f"• 任务分布: {domain_text}")

        if snapshot.execution_counts:
            execution_text = ", ".join(
                f"{mode}:{count}" for mode, count in snapshot.execution_counts.items()
            )
            lines.append(f"• 搜索执行: {execution_text}")

        if snapshot.search_focuses:
            lines.append("• 搜索焦点: " + " | ".join(snapshot.search_focuses[:3]))

        if snapshot.customer_focus:
            customer_text = ", ".join(
                f"{label}({count})"
                for label, count in Counter(snapshot.customer_focus).most_common()
            )
            lines.append(f"• 客户关注: {customer_text}")

        if snapshot.platform_focus:
            platform_text = ", ".join(
                f"{label}({count})"
                for label, count in Counter(snapshot.platform_focus).most_common()
            )
            lines.append(f"• 平台关注: {platform_text}")

        if snapshot.memory_status_counts:
            memory_status_text = ", ".join(
                f"{label}({count})" for label, count in sorted(snapshot.memory_status_counts.items())
            )
            lines.append(f"• 记忆状态: {memory_status_text}")

        if snapshot.next_actions:
            lines.append("建议下一步动作")
            if snapshot.next_actions.get("insight"):
                lines.append(f"• 客户洞察: {snapshot.next_actions['insight']}")
            if snapshot.next_actions.get("content"):
                lines.append(f"• 内容动作: {snapshot.next_actions['content']}")
            if snapshot.next_actions.get("ops"):
                lines.append(f"• 技术状态: {snapshot.next_actions['ops']}")

        lines.append("最近任务")
        if snapshot.recent_tasks:
            for item in snapshot.recent_tasks:
                line = f"• [{item.status}] {item.intent[:70]}"
                if item.followup:
                    line = f"{line} | 跟进: {item.followup}"
                lines.append(line)
        else:
            lines.append("• 暂无任务")

        lines.append("重点记忆")
        if snapshot.highlight_memories:
            for item in snapshot.highlight_memories:
                lines.append(f"• {item.content[:70]} | 状态: {item.status}")
        else:
            lines.append("• 暂无持久记忆")

        lines.append("建议入口")
        lines.append("• 推荐指令: " + " | ".join(snapshot.recommended_commands))
        lines.append("[OK]")

        return "\n".join(lines)

    def add_memory(
        self,
        content: str,
        source: str = "astrbot",
        importance: float = 0.7,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        inferred_tags = self._collect_keyword_labels([content])
        merged_tags = list(dict.fromkeys((tags or []) + inferred_tags))
        return self.memory_store.add_memory(
            content=content,
            source=source,
            importance=importance,
            tags=merged_tags,
            metadata=metadata,
        )

    def _store_brief_memory(self, kind: str, query: str, text: str) -> str:
        return self.add_memory(
            content=text,
            source="brief_auto",
            importance=0.75,
            metadata={
                "brief_kind": kind,
                "brief_query": query,
            },
        )

    def _brief_preview_from_text(self, text: str) -> str:
        ignored = {
            "今日新闻",
            "今日热点",
            "客户上下文",
            "建议下一步",
            "竞品速览",
            "最新动态",
            "平台热点",
            "平台动态",
            "历史线索",
        }
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line == "[OK]" or line.startswith("【AstrBot"):
                continue
            if line.startswith("• 主题:") or line.startswith("• 品牌:"):
                continue
            if line in ignored:
                continue
            return line[:120]
        return ""

    def _build_brief_source_label(self, result: Result) -> str:
        if not result.task_id:
            return "结果待确认"
        task = self.engine.task_store.get(result.task_id)
        if not task:
            return "结果待确认"
        mode = self._summarize_task_execution_mode(task)
        if mode == "opencli_live":
            return "实时数据"
        if mode == "opencli_fallback":
            return "回退结果"
        return "任务结果"

    def _infer_request_command(self, request_text: str) -> tuple[str, str, str, int | None]:
        lowered = request_text.lower()
        cleaned = request_text
        for token in self.NOISE_TOKENS:
            cleaned = cleaned.replace(token, " ")
        cleaned = " ".join(cleaned.split()).strip() or request_text.strip()
        interval_minutes = 1440 if any(token in request_text for token in self.TRACKING_HINTS) else None

        for platform in self.PLATFORM_HINTS:
            if platform.lower() in lowered:
                focus = self._extract_request_focus(cleaned, exclude=[platform])
                prompt = platform if not focus else f"{platform} {focus}"
                label = "平台热点订阅" if interval_minutes is not None else "平台热点简报"
                return ("oc2_platform_brief", prompt, label, interval_minutes)

        if any(hint in request_text for hint in self.COMPETITOR_HINTS):
            prompt = cleaned
            for hint in ["竞品", "对手", "友商", "品牌", "动态", "动向", "动静", "新动静", "情况", "观察", "看看", "分析", "日报", "简报", "线索", "内容", "有啥", "有什么", "有没有", "热度怎么样", "怎么样", "传播方向", "方向", "点子", "创意", "怎么做", "值得做", "值不值得做", "打法", "切入点", "值得关注", "关注点", "适不适合做", "能不能做"]:
                prompt = prompt.replace(hint, " ")
            prompt = " ".join(prompt.split()).strip() or cleaned
            label = "竞品订阅" if interval_minutes is not None else "竞品简报"
            return ("oc2_competitor_brief", prompt, label, interval_minutes)

        prompt = cleaned
        for hint in ["新闻", "热点", "趋势", "方向", "动态", "动向", "动静", "新动静", "日报", "简报", "线索", "创意", "方案", "盘点", "汇总", "总结", "消息", "热度怎么样", "怎么样", "值得关注", "关注点", "适不适合做", "能不能做", "有没有"]:
            prompt = prompt.replace(hint, " ")
        prompt = " ".join(prompt.split()).strip() or cleaned
        label = "每日简报订阅" if interval_minutes is not None else "每日简报"
        return ("oc2_daily_brief", prompt, label, interval_minutes)

    def _extract_request_focus(self, cleaned_text: str, exclude: list[str] | None = None) -> str:
        exclude = exclude or []
        lowered = cleaned_text.lower()
        for label, keywords in self.PROJECT_KEYWORDS.items():
            if label in {"平台热点", "营销策划"}:
                continue
            if any(keyword.lower() in lowered for keyword in keywords):
                if label not in exclude:
                    return label
        for hint in ["比亚迪", "特斯拉", "理想", "蔚来", "小鹏"]:
            if hint in cleaned_text and hint not in exclude:
                return hint
        return ""

    def _detect_request_use(self, request_text: str, interval_minutes: int | None) -> str:
        if any(token in request_text for token in self.CREATIVE_HINTS):
            return "持续跟踪与创意线索" if interval_minutes is not None else "创意方向"
        return "持续跟踪" if interval_minutes is not None else "信息简报"

    def _store_request_memory(
        self,
        request_text: str,
        workflow_label: str,
        prompt: str,
        execution_text: str,
        command_text: str,
        result_use: str,
    ) -> str:
        content = (
            "OC2 需求识别记录\n"
            f"原始需求: {request_text}\n"
            f"工作流: {workflow_label}\n"
            f"主题: {prompt}\n"
            f"执行方式: {execution_text}\n"
            f"结果用途: {result_use}\n"
            f"转换结果: {command_text}"
        )
        return self.add_memory(
            content=content,
            source="request_auto",
            importance=0.65,
            metadata={
                "request_text": request_text,
                "workflow_label": workflow_label,
                "request_prompt": prompt,
                "execution_text": execution_text,
                "command_text": command_text,
                "result_use": result_use,
            },
        )

    def _capture_task_memory(self, result: Result) -> str | None:
        if not result.is_ok() or not result.task_id:
            return None

        task = self.engine.task_store.get(result.task_id)
        if not task or task.domain != "marketing":
            return None

        category = self.query_service.categorize_task(task)
        if category not in {"客户洞察", "内容生产", "分析复盘"}:
            return None

        if self.query_service.has_task_memory(task.id):
            return None

        execution_mode = self.query_service.summarize_task_execution_mode(task)
        memory_text = self.query_service.build_task_memory_content(task, category, execution_mode)
        importance = self.query_service.calculate_task_memory_importance(category, execution_mode)
        metadata = {
            "auto_captured": True,
            "from_task_id": task.id,
            "task_domain": task.domain,
            "task_status": task.status.value,
            "task_category": category,
            "execution_mode": execution_mode,
        }
        if category == "客户洞察" or execution_mode == "opencli_live":
            metadata["memory_tier"] = "promoted"
            metadata["promotion_reason"] = "高价值客户洞察自动沉淀"

        return self.add_memory(
            content=memory_text,
            source="task_auto",
            importance=importance,
            tags=[category],
            metadata=metadata,
        )

    def _capture_short_term_memory(
        self,
        command_name: str,
        prompt: str | None,
        result: Result,
    ) -> str | None:
        if not result.task_id:
            return None
        task = self.engine.task_store.get(result.task_id)
        if not task:
            return None

        content_parts = [
            f"命令: /{command_name} {(prompt or '').strip()}".rstrip(),
            f"任务: {task.intent[:120]}",
        ]
        preview = self._result_to_text(result).strip()
        if preview:
            content_parts.append(f"结果: {preview[:160]}")

        tags = self.query_service.collect_keyword_labels(
            [task.intent, preview, " ".join(getattr(task, "logs", [])[-3:])]
        )
        return self.short_term_memory.add_entry(
            content=" | ".join(content_parts),
            category="recent_task",
            domain=task.domain,
            tags=tags,
            metadata={
                "task_id": task.id,
                "command_name": command_name,
                "prompt": prompt or "",
                "task_status": task.status.value,
            },
        )

    def compress_short_term_memory(
        self,
        query: str | None = None,
        domain: str | None = "marketing",
        limit: int = 10,
    ) -> str:
        result = self.memory_compressor.build_summary(query=query, domain=domain, limit=limit)
        return result.summary_text

    def promote_short_term_memory(
        self,
        query: str | None = None,
        domain: str | None = "marketing",
        limit: int = 10,
    ) -> str:
        summary = self.memory_compressor.build_summary(query=query, domain=domain, limit=limit)
        decision, memory_id = self.memory_promotion.promote(summary, domain=domain, query=query)
        if not decision.should_promote:
            return f"未提升到长期记忆: {decision.reason}"
        return f"已提升到长期记忆: {decision.category} | {decision.reason} | memory_id={memory_id}"

    def get_memory_summary_text(self, limit: int = 20) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 持久记忆：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        snapshot = self.dashboard_service.get_workspace_snapshot(task_limit=limit, memory_limit=limit).memory_summary
        lines = ["【AstrBot🗂️】OC2 持久记忆："]
        if not snapshot.items:
            lines.append("• 暂无持久记忆")
            lines.append("[OK]")
            return "\n".join(lines)

        if snapshot.priority_lines:
            lines.append("优先记忆")
            for line in snapshot.priority_lines:
                lines.append(f"• {line}")

        if snapshot.category_counts:
            top_categories = ", ".join(
                f"{label}({count})"
                for label, count in Counter(snapshot.category_counts).most_common(5)
            )
            lines.append(f"• 记忆统计: {top_categories}")

        if snapshot.status_counts:
            status_text = ", ".join(
                f"{label}({count})" for label, count in sorted(snapshot.status_counts.items())
            )
            lines.append(f"• 记忆状态: {status_text}")

        for index, item in enumerate(snapshot.items, 1):
            stars = "⭐" * max(1, int(item.importance * 5))
            tag_text = f" ({', '.join(item.tags)})" if item.tags else ""
            lines.append(f"• {index}. [{stars}]{tag_text} {item.content[:80]} | 状态: {item.status}")
        lines.append(f"• 推荐操作: {snapshot.recommended_action}")
        lines.append("[OK]")
        return "\n".join(lines)

    def search_memory_text(self, query: str, limit: int = 10) -> str:
        if not is_harness_enabled():
            return "【AstrBot🔴】OC2 持久记忆搜索：\n• 状态: OFFLINE ❌\n• 说明: Harness 当前已关闭\n[OK]"

        snapshot = self.query_service.search_memory_snapshot(query, limit=limit)
        lines = ["【AstrBot🔎】OC2 持久记忆搜索：", f"• 搜索: {query}"]
        if not snapshot.items:
            lines.append("• 未找到匹配的持久记忆")
            lines.append("[OK]")
            return "\n".join(lines)

        lines.append("搜索结果")
        for index, item in enumerate(snapshot.items, 1):
            stars = "⭐" * max(1, int(item.importance * 5))
            tag_text = f" ({', '.join(item.tags)})" if item.tags else ""
            lines.append(f"• {index}. [{stars}]{tag_text} {item.content[:100]} | 状态: {item.status}")
            if item.followup:
                lines.append(f"  • 跟进: {item.followup}")
        lines.append(f"• 推荐延伸: {snapshot.extension_hint}")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_brief_history_text(self, limit: int = 10, kind: str | None = None) -> str:
        memories = self.memory_store.list_memories(limit=max(limit * 3, 20), source="brief_auto")
        if kind:
            memories = [memory for memory in memories if memory.metadata.get("brief_kind") == kind]
        memories = memories[:limit]

        lines = ["【AstrBot🗂️】OC2 简报历史：", f"• 类型: {kind or '全部'}"]
        if not memories:
            lines.append("• 暂无简报历史")
            lines.append("[OK]")
            return "\n".join(lines)

        lines.append("最近简报")
        for memory in memories:
            brief_kind = memory.metadata.get("brief_kind", "unknown")
            brief_query = memory.metadata.get("brief_query", "")
            preview = self._brief_preview_from_text(memory.content)
            request_memory = self._find_request_memory_for_brief(memory)
            lines.append(f"• {brief_kind} | {brief_query} | {memory.id}")
            if request_memory:
                lines.append(f"  • 需求: {request_memory.metadata.get('request_text', '')}")
            if preview:
                lines.append(f"  • {preview}")
        lines.append("[OK]")
        return "\n".join(lines)

    def get_brief_detail_text(self, memory_id: str) -> str:
        memories = self.memory_store.list_memories(limit=500, source="brief_auto")
        memory = next((item for item in memories if item.id == memory_id), None)
        lines = ["【AstrBot📄】OC2 简报详情："]
        if not memory:
            lines.append("• 未找到对应简报")
            lines.append("[OK]")
            return "\n".join(lines)

        lines.append(f"• ID: {memory.id}")
        lines.append(f"• 类型: {memory.metadata.get('brief_kind', 'unknown')}")
        lines.append(f"• 主题: {memory.metadata.get('brief_query', '')}")
        request_memory = self._find_request_memory_for_brief(memory)
        if request_memory:
            lines.append(f"• 原始需求: {request_memory.metadata.get('request_text', '')}")
            lines.append(f"• 识别工作流: {request_memory.metadata.get('workflow_label', '')}")
            lines.append(f"• 执行方式: {request_memory.metadata.get('execution_text', '')}")
            lines.append(f"• 结果用途: {request_memory.metadata.get('result_use', '')}")
        lines.append("内容")
        for raw_line in memory.content.splitlines():
            line = raw_line.rstrip()
            if line:
                lines.append(line)
        lines.append("[OK]")
        return "\n".join(lines)

    def _find_request_memory_for_brief(self, brief_memory):
        brief_kind = str(brief_memory.metadata.get("brief_kind", ""))
        brief_query = str(brief_memory.metadata.get("brief_query", ""))
        if not brief_kind or not brief_query:
            return None

        workflow_map = {
            "daily": "每日简报",
            "competitor": "竞品简报",
            "platform": "平台热点简报",
        }
        expected_workflow = workflow_map.get(brief_kind, "")
        request_memories = self.memory_store.list_memories(limit=100, source="request_auto")
        for memory in request_memories:
            if memory.metadata.get("request_prompt") != brief_query:
                continue
            workflow_label = str(memory.metadata.get("workflow_label", ""))
            if expected_workflow and expected_workflow not in workflow_label:
                continue
            return memory
        return None

    def _collect_keyword_labels(self, texts: list[str]) -> list[str]:
        labels: list[str] = []
        joined = "\n".join(texts)
        for label, keywords in self.PROJECT_KEYWORDS.items():
            if any(keyword.lower() in joined.lower() for keyword in keywords):
                labels.append(label)
        return labels

    def _categorize_task(self, task) -> str:
        intent = (task.intent or "").lower()
        mode = self._summarize_task_execution_mode(task)

        if mode == "opencli_fallback":
            return "技术回退"

        if any(keyword in intent for keyword in ["mt_copy", "mt_marketing", "mt_event", "mt_pr"]):
            return "内容生产"

        if any(keyword in intent for keyword in ["mtoc_news", "mtoc_hot", "mtoc_data", "mtoc_competitor"]):
            return "客户洞察"

        if any(keyword in intent for keyword in ["analytics", "分析", "报告", "data"]):
            return "分析复盘"

        return "通用执行"

    def _build_priority_task_summary(self, tasks: list) -> list[str]:
        fallback_tasks = [task for task in tasks if self._categorize_task(task) == "技术回退"]
        insight_tasks = [task for task in tasks if self._categorize_task(task) == "客户洞察"]
        lines: list[str] = []

        if fallback_tasks:
            task = fallback_tasks[0]
            lines.append(
                f"技术回退待处理: {task.intent[:50]} | 建议: 检查 OpenCLI / Browser Bridge 连接"
            )

        if insight_tasks:
            task = insight_tasks[0]
            focus = self._infer_task_followup_focus(task)
            lines.append(
                f"高价值客户洞察: {task.intent[:50]} | 建议: 继续跟进 {focus}"
            )

        return lines

    def _infer_task_followup_focus(self, task) -> str:
        command_text = " ".join(
            str(step.params.get("command", "")) for step in task.plan if step.tool == "opencli"
        ).lower()
        for label in ["小红书", "抖音", "微博", "知乎"]:
            if label.lower() in command_text:
                return label
        for label in ["柳州五菱", "柳汽东风", "新能源汽车"]:
            if label.lower() in command_text or label.lower() in (task.intent or "").lower():
                return label
        return "重点平台与客户关键词"

    def _build_task_inline_suggestion(self, task) -> str:
        category = self._categorize_task(task)
        if category == "技术回退":
            return "检查 OpenCLI / Browser Bridge"
        if category == "客户洞察":
            return f"继续跟进 {self._infer_task_followup_focus(task)}"
        if category == "内容生产":
            return "补充多版本内容和发布角度"
        if category == "分析复盘":
            return "整理结论并补充关键指标"
        return ""

    def _build_memory_inline_suggestion(self, memory) -> str:
        content = (memory.content or "").lower()
        tags = {tag.lower() for tag in getattr(memory, "tags", [])}

        for label in ["小红书", "抖音", "微博", "知乎"]:
            if label.lower() in content:
                return f"继续跟进 {label} 平台反馈和高互动样本"

        if any(tag in tags for tag in ["柳州五菱", "柳汽东风", "新能源汽车"]) or any(
            keyword in content for keyword in ["柳州五菱", "柳汽东风", "新能源汽车"]
        ):
            for label in ["柳州五菱", "柳汽东风", "新能源汽车"]:
                if label.lower() in content or label.lower() in tags:
                    return f"围绕 {label} 补充最新客户情报和内容线索"
            return "补充客户项目最新情报"

        if any(tag in tags for tag in ["平台热点", "营销策划"]) or any(
            keyword in content for keyword in ["小红书", "抖音", "微博", "知乎"]
        ):
            return "继续跟进重点平台反馈和高互动样本"

        return "结合当前项目继续补充可复用洞察"

    def _build_priority_memory_summary(self, memories: list) -> list[str]:
        lines: list[str] = []

        customer_memory = next(
            (
                memory for memory in memories
                if any(tag in getattr(memory, "tags", []) for tag in ["柳州五菱", "柳汽东风", "新能源汽车"])
            ),
            None,
        )
        if customer_memory:
            lines.append(
                f"客户项目优先: {customer_memory.content[:40]} | 建议: {self._build_memory_inline_suggestion(customer_memory)}"
            )

        platform_memory = next(
            (
                memory for memory in memories
                if any(tag in getattr(memory, "tags", []) for tag in ["平台热点", "营销策划"])
            ),
            None,
        )
        if platform_memory and platform_memory is not customer_memory:
            lines.append(
                f"平台热点优先: {platform_memory.content[:40]} | 建议: {self._build_memory_inline_suggestion(platform_memory)}"
            )

        return lines

    def _has_task_memory(self, task_id: str) -> bool:
        for memory in self.memory_store.list_memories(limit=200):
            if str(getattr(memory, "metadata", {}).get("from_task_id", "")) == task_id:
                return True
        return False

    def _build_task_memory_content(self, task, category: str, execution_mode: str) -> str:
        parts = [task.intent[:80]]
        if category:
            parts.append(f"分类: {category}")
        if execution_mode and execution_mode != "standard":
            parts.append(f"执行: {execution_mode}")
        if task.logs:
            latest_log = str(task.logs[-1]).strip()
            if latest_log:
                parts.append(f"最近进展: {latest_log[:80]}")
        if task.result:
            result_text = str(task.result).strip()
            if result_text:
                parts.append(f"结果摘要: {result_text[:100]}")
        return " | ".join(parts)

    @staticmethod
    def _calculate_task_memory_importance(category: str, execution_mode: str) -> float:
        if execution_mode == "opencli_live":
            return 0.9
        if category == "客户洞察":
            return 0.85
        if category == "分析复盘":
            return 0.75
        return 0.7

    @staticmethod
    def _summarize_task_execution_mode(task) -> str:
        step_execution = getattr(task, "metadata", {}).get("step_execution", {})
        if isinstance(step_execution, dict):
            for details in step_execution.values():
                if not isinstance(details, dict):
                    continue
                tool = details.get("tool")
                status = details.get("status")
                if tool == "opencli" and status == "opencli_live":
                    return "opencli_live"
                if tool == "opencli" and status in {"web_fallback", "llm_fallback"}:
                    return "opencli_fallback"

        opencli_steps = [step for step in task.plan if step.tool == "opencli"]
        if not opencli_steps:
            return "standard"

        for step in opencli_steps:
            step_result = str(step.result or "")
            if "OpenCLI 实时搜索结果" in step_result:
                return "opencli_live"
            if "已回退到模板搜索结果" in step_result:
                return "opencli_fallback"
        return "opencli_planned"

    def _collect_keyword_counts(self, texts: list[str]) -> Counter:
        counts: Counter = Counter()
        lowered_texts = [text.lower() for text in texts]
        for label, keywords in self.PROJECT_KEYWORDS.items():
            for text in lowered_texts:
                if any(keyword.lower() in text for keyword in keywords):
                    counts[label] += 1
        return counts

    def _collect_opencli_search_focuses(self, tasks: list) -> list[str]:
        focuses: list[str] = []
        for command in self._extract_opencli_commands(tasks):
            focus = command
            if focus.startswith("google search "):
                focus = focus[len("google search "):]
            if focus not in focuses:
                focuses.append(focus[:80])
        return focuses

    def _collect_search_label_counts(self, tasks: list, labels: list[str]) -> Counter:
        command_text = "\n".join(self._extract_opencli_commands(tasks)).lower()
        counts: Counter = Counter()
        for label in labels:
            keywords = self.PROJECT_KEYWORDS.get(label, [])
            hits = sum(1 for keyword in keywords if keyword.lower() in command_text)
            if hits:
                counts[label] = hits
        return counts

    def _collect_platform_focus_counts(self, tasks: list) -> Counter:
        command_text = "\n".join(self._extract_opencli_commands(tasks)).lower()
        platform_keywords = {
            "小红书": ["小红书"],
            "抖音": ["抖音"],
            "微博": ["微博"],
            "知乎": ["知乎"],
            "视频号": ["视频号"],
            "B站": ["b站", "哔哩哔哩"],
        }
        counts: Counter = Counter()
        for label, keywords in platform_keywords.items():
            hits = sum(1 for keyword in keywords if keyword.lower() in command_text)
            if hits:
                counts[label] = hits
        return counts

    @staticmethod
    def _extract_opencli_commands(tasks: list) -> list[str]:
        commands: list[str] = []
        for task in tasks:
            for step in task.plan:
                if step.tool != "opencli":
                    continue
                command = str(step.params.get("command", "")).strip()
                if not command:
                    continue
                commands.append(command)
        return commands

    @staticmethod
    def _build_next_action_suggestions(
        customer_focus: Counter,
        platform_focus: Counter,
        execution_counts: Counter,
    ) -> dict[str, str]:
        suggestions: dict[str, str] = {}

        if customer_focus:
            top_customer, _ = customer_focus.most_common(1)[0]
            if platform_focus:
                top_platforms = "、".join(label for label, _ in platform_focus.most_common(2))
                suggestions["insight"] = f"继续跟进 {top_customer} 在 {top_platforms} 的最新传播动向"
            else:
                suggestions["insight"] = f"继续补充 {top_customer} 的平台舆情与内容线索"

        if execution_counts.get("opencli_fallback"):
            suggestions["ops"] = "检查 OpenCLI 或 Browser Bridge 状态，优先恢复实时搜索"

        if "小红书" in platform_focus and "抖音" in platform_focus:
            suggestions["content"] = "对比小红书种草内容与抖音短视频话题，提炼统一传播主题"
        elif platform_focus:
            top_platform, _ = platform_focus.most_common(1)[0]
            suggestions["content"] = f"围绕 {top_platform} 补一轮高互动内容样本和竞品案例"

        if not suggestions and execution_counts.get("opencli_live"):
            suggestions["content"] = "继续扩展实时搜索关键词，补充竞品和媒体视角"

        return suggestions

    def _build_raw_event(self, command_name: str, prompt: str | None, event: Any = None) -> dict[str, Any]:
        command_text = f"/{command_name}"
        if prompt:
            command_text = f"{command_text} {prompt.strip()}"

        return {
            "id": str(getattr(event, "message_id", "")),
            "message_id": str(getattr(event, "message_id", "")),
            "content": command_text,
            "message": command_text,
            "text": command_text,
            "user_id": str(getattr(event, "sender_id", "")),
            "sender_id": str(getattr(event, "sender_id", "")),
            "sender_name": getattr(event, "sender_nickname", ""),
            "group_id": str(getattr(event, "group_id", "")),
            "chat_id": str(getattr(event, "group_id", "")),
            "platform": str(getattr(event, "platform", "astrbot")),
        }

    def _session_key(self, event: Any = None) -> str:
        sender = str(getattr(event, "sender_id", "") or "anonymous")
        group = str(getattr(event, "group_id", "") or "direct")
        return f"{group}:{sender}"

    def _extract_uploaded_file(self, event: Any = None) -> tuple[str, str]:
        if event is None:
            return "", ""

        direct_path = str(getattr(event, "file_path", "") or "")
        direct_name = str(getattr(event, "file_name", "") or "")
        if direct_path:
            return direct_path, direct_name or direct_path.split("/")[-1]

        file_obj = getattr(event, "file", None)
        if isinstance(file_obj, dict):
            path = str(file_obj.get("path", "") or file_obj.get("file_path", "") or "")
            name = str(file_obj.get("name", "") or file_obj.get("filename", "") or "")
            if path:
                return path, name or path.split("/")[-1]
        elif isinstance(file_obj, str) and file_obj.strip():
            return file_obj.strip(), file_obj.strip().split("/")[-1]

        for attr_name in ("attachments", "files"):
            items = getattr(event, attr_name, None) or []
            if items:
                item = items[0]
                if isinstance(item, dict):
                    path = str(item.get("path", "") or item.get("file_path", "") or "")
                    name = str(item.get("name", "") or item.get("filename", "") or "")
                    if path:
                        return path, name or path.split("/")[-1]
        return "", ""

    def _build_file_category_prompt(self, payload: dict[str, Any]) -> str:
        lines = [
            "【AstrBot📎】OC2 资料归档：",
            f"• 已收到文件: {payload.get('source_name', '')}",
            f"• 编号: {payload.get('upload_id', '')}",
        ]
        if payload.get("brand"):
            lines.append(f"• 归属提示: {payload.get('brand')}")
        if payload.get("recommended_category"):
            lines.append(f"• 推荐分类: {payload.get('recommended_category')}")
        lines.append("")
        lines.append("请选择文件类型")
        for key, (_, label) in self.FILE_TYPE_OPTIONS.items():
            lines.append(f"• {key}. {label}")
        lines.append("• 请回复: /oc2_file_reply A")
        lines.append("[OK]")
        return "\n".join(lines)

    def _build_file_owner_prompt(self, session: dict[str, Any]) -> str:
        lines = [
            "【AstrBot📎】OC2 资料归档：",
            f"• 已选择类型: {session.get('category_label', '')}",
            "请选择归属对象",
        ]
        for key, label in self.FILE_OWNER_OPTIONS.items():
            lines.append(f"• {key}. {label}")
        lines.append("• 请回复: /oc2_file_reply 1")
        lines.append("[OK]")
        return "\n".join(lines)

    def _build_file_note_prompt(self, session: dict[str, Any]) -> str:
        return (
            "【AstrBot📎】OC2 资料归档：\n"
            f"• 文件类型: {session.get('category_label', '')}\n"
            f"• 归属对象: {session.get('owner_name', '')}\n"
            "• 请输入备注内容；如无备注，请回复: /oc2_file_reply 无\n"
            "[OK]"
        )

    def _reply_file_category(self, session: dict[str, Any], reply: str) -> str:
        code = reply.upper()
        if code not in self.FILE_TYPE_OPTIONS:
            return "【AstrBot📎】OC2 资料归档：\n• 文件类型无效\n• 请回复 A-H 或 Z\n[OK]"
        category_key, category_label = self.FILE_TYPE_OPTIONS[code]
        if category_key == "custom":
            session["step"] = "custom_category"
            return "【AstrBot📎】OC2 资料归档：\n• 请输入自定义文件类型名称\n• 例如: 会议纪要 / 直播脚本 / 素材清单\n[OK]"
        session["category"] = category_key
        session["category_label"] = category_label
        session["step"] = "owner"
        return self._build_file_owner_prompt(session)

    def _reply_file_custom_category(self, session: dict[str, Any], reply: str) -> str:
        label = reply.strip()
        if not label:
            return "【AstrBot📎】OC2 资料归档：\n• 自定义文件类型不能为空\n[OK]"
        session["category"] = label
        session["category_label"] = label
        session["step"] = "owner"
        return self._build_file_owner_prompt(session)

    def _reply_file_owner(self, session: dict[str, Any], reply: str) -> str:
        code = reply.strip()
        if code not in self.FILE_OWNER_OPTIONS:
            return "【AstrBot📎】OC2 资料归档：\n• 归属对象无效\n• 请回复 1-6 或 9\n[OK]"
        label = self.FILE_OWNER_OPTIONS[code]
        if code == "9":
            session["step"] = "custom_owner"
            return "【AstrBot📎】OC2 资料归档：\n• 请输入自定义归属对象名称\n• 例如: 广汽埃安 / 五菱星光 / 视频号\n[OK]"
        session["owner_name"] = "general" if code == "6" else label
        session["step"] = "note"
        return self._build_file_note_prompt(session)

    def _reply_file_custom_owner(self, session: dict[str, Any], reply: str) -> str:
        label = reply.strip()
        if not label:
            return "【AstrBot📎】OC2 资料归档：\n• 自定义归属对象不能为空\n[OK]"
        session["owner_name"] = label
        session["step"] = "note"
        return self._build_file_note_prompt(session)

    def _reply_file_note(self, session: dict[str, Any], reply: str) -> str:
        note = "" if reply.strip() in {"无", "none", "NONE"} else reply.strip()
        result = self.knowledge_ingest.confirm(
            session["upload_id"],
            session["category"],
            brand=session.get("owner_name") or session.get("brand_hint") or "general",
            category_label=session.get("category_label"),
        )
        result["note"] = note
        self.memory_store.add_memory(
            content=(
                f"资料归档: {result.get('source_name', '')} | 类型: {result.get('category_label', result.get('category', ''))} "
                f"| 归属: {result.get('brand', 'general')}"
                + (f" | 备注: {note}" if note else "")
            ),
            source="file_ingest_auto",
            importance=0.72,
            tags=["资料归档", result.get("brand", "general"), result.get("category", "")],
            metadata={
                "upload_id": result.get("upload_id", session.get("upload_id", "")),
                "source_name": result.get("source_name", ""),
                "category": result.get("category", ""),
                "category_label": result.get("category_label", ""),
                "brand": result.get("brand", "general"),
                "final_path": result.get("final_path", ""),
                "note": note,
            },
        )
        self._file_ingest_sessions.pop(session.get("session_key", ""), None)
        lines = [
            "【AstrBot✅】OC2 资料归档完成：",
            f"• 文件: {result.get('source_name', '')}",
            f"• 类型: {result.get('category_label', result.get('category', ''))}",
            f"• 归属: {result.get('brand', 'general')}",
        ]
        if note:
            lines.append(f"• 备注: {note}")
        lines.append(f"• 存储位置: {result.get('final_path', '')}")
        lines.append("[OK]")
        return "\n".join(lines)

    @staticmethod
    def _result_to_text(result: Result) -> str:
        if result.result_type in (ResultType.SUCCESS, ResultType.PARTIAL):
            return result.content or "（无返回内容）"

        if result.error_message:
            return result.error_message

        return result.content or "请求处理失败"

    @staticmethod
    def _compact_text_block(text: str, max_lines: int = 5) -> list[str]:
        ignored_contains = (
            "热点营销策划",
            "新闻营销方案",
            "竞品分析策略",
            "离线回退",
            "完整营销方案",
            "营销分析结果",
            "可直接使用",
            "请基于",
            "以下真实数据",
        )
        lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line == "[OK]":
                continue
            if line.startswith("【AstrBot") or line.startswith("JW-Claw"):
                continue
            if line.startswith("建议入口") or line.startswith("推荐指令") or line.startswith("推荐下一步"):
                continue
            if line.startswith(("一、", "二、", "三、", "四、", "五、", "六、")):
                continue
            if line.startswith(("1.", "2.", "3.", "4.", "5.")) and any(
                keyword in line for keyword in ("摘要", "分析", "建议", "方向", "方案")
            ):
                continue
            if any(token in line for token in ignored_contains):
                continue
            if not line.startswith(("•", "-", "1.", "2.", "3.", "4.", "5.")):
                line = f"• {line}"
            lines.append(line[:180])
            if len(lines) >= max_lines:
                break
        if not lines:
            return ["• （暂无内容）"]
        return lines

    @staticmethod
    def is_enabled() -> bool:
        return is_harness_enabled()

    @staticmethod
    def is_debug_enabled() -> bool:
        return is_harness_enabled() and is_harness_debug_enabled()
