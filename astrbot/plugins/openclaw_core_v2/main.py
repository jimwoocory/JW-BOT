import logging
import sys
import os

# 添加 HarnessEngineering 到 Python 路径
_harness_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'HarnessEngineering', 'src')
if _harness_path not in sys.path:
    sys.path.insert(0, _harness_path)
    logging.getLogger("openclaw.plugins.openclaw_core_v2").info(f"Added to path: {_harness_path}")

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from data.plugins._shared_ops_helpers import (
    build_available_modes_text,
    build_category_summary_lines,
    build_error_text,
    build_feature_toggled_text,
    build_feature_toggle_prompt,
    build_feature_flags_text,
    build_harness_disabled_text,
    build_memory_added_text,
    build_memory_lines,
    build_memory_search_empty_text,
    build_memory_search_header,
    build_missing_input_prompt,
    build_permission_added_text,
    build_permission_mode_set_text,
    build_permissions_text,
    build_priority_focus_text,
    build_project_context_prompt,
    build_section_lines,
    build_task_created_text,
    build_task_lines,
    build_usage_text,
    collect_unique_labels,
    parse_permission_allow,
    resolve_permission_mode,
)
from jw_claw.astrbot import (
    HarnessAstrBotBridge,
    AstrBotLLMAdapter,
    is_astrbot_provider_bridge_enabled,
    is_frontend_local_fallback_enabled,
    is_harness_debug_enabled,
    is_harness_enabled,
)
from data.plugins.openclaw_connector.gateway_contract import (
    GatewayRequestSpec,
    build_harness_competitor_brief_request,
    build_harness_daily_brief_request,
    build_harness_file_pending_request,
    build_harness_file_reply_request,
    build_harness_file_search_request,
    build_harness_file_text_request,
    build_harness_platform_brief_request,
    build_harness_request_request,
)
from data.plugins.openclaw_connector.settings import load_connector_settings
from .core import (
    PermissionManager,
    TaskManager,
    MemoryManager,
    get_feature_status,
    enable_feature,
    disable_feature,
    PermissionMode,
    TaskType,
)

logger = logging.getLogger("openclaw.plugins.openclaw_core_v2")


def _strip_self_command_prefix(raw_text: str, command_name: str) -> str:
    text = (raw_text or "").strip()
    for prefix in (f"/{command_name}", command_name):
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            return text[len(prefix):].strip()
    return text


@star.register("openclaw_core_v2", "OpenClaw Team", "Openclaw Core v2 - 模块化插件", "2.0.0")
class OpenClawCoreV2Plugin(star.Star):
    def __init__(self, context):
        super().__init__(context)
        self.harness_bridge = HarnessAstrBotBridge()
        gateway_settings = load_connector_settings()
        self.gateway_api_url = gateway_settings["api_url"]
        self.gateway_api_token = gateway_settings["api_token"]
        self.gateway_timeout = int(gateway_settings["timeout"])
        if is_astrbot_provider_bridge_enabled():
            adapter = AstrBotLLMAdapter(context)
            logger.info(f"AstrBotLLMAdapter created (supports lazy init)")
            self.harness_bridge.set_llm_client(adapter)
            logger.info("✅ AstrBotLLMAdapter 已设置到 HarnessBridge (将在首次调用时初始化 provider)")
        else:
            logger.warning("⚠️ astrbot provider bridge 未启用 (OPENCLAW_JW_CLAW_USE_ASTRBOT_PROVIDER)")
        self.permission_manager = PermissionManager()
        self.task_manager = TaskManager()
        self.memory_manager = MemoryManager()
        logger.info("插件加载成功")

    async def _invoke_gateway_text(self, request_spec: GatewayRequestSpec) -> str:
        headers = {
            "Authorization": f"Bearer {self.gateway_api_token}",
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.gateway_api_url + request_spec.path,
                json=request_spec.payload,
                headers=headers,
                timeout=self.gateway_timeout,
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"HTTP {resp.status}: {error_text}")
                data = await resp.json()
        result = data.get("reply") or data.get("text")
        if not result:
            raise RuntimeError("未返回结果")
        return str(result)

    async def _get_request_text_via_gateway_or_bridge(self, request_text: str, event: AstrMessageEvent) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_request_request(request_text))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 request 失败，回退本地 Harness: %s", exc)
            return await self.harness_bridge.get_request_text(request_text, event=event)

    async def _get_daily_brief_via_gateway_or_bridge(self, query: str, event: AstrMessageEvent) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_daily_brief_request(query))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 daily brief 失败，回退本地 Harness: %s", exc)
            return await self.harness_bridge.get_daily_brief_text(query, event=event)

    async def _get_competitor_brief_via_gateway_or_bridge(self, brand: str, event: AstrMessageEvent) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_competitor_brief_request(brand))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 competitor brief 失败，回退本地 Harness: %s", exc)
            return await self.harness_bridge.get_competitor_brief_text(brand, event=event)

    async def _get_platform_brief_via_gateway_or_bridge(self, topic: str, event: AstrMessageEvent) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_platform_brief_request(topic))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 platform brief 失败，回退本地 Harness: %s", exc)
            return await self.harness_bridge.get_platform_brief_text(topic, event=event)

    async def _start_file_text_via_gateway_or_bridge(self, filename: str, content: str, event: AstrMessageEvent) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_file_text_request(filename, content))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 file text 失败，回退本地 Harness: %s", exc)
            return self.harness_bridge.start_file_ingest_from_text(filename, content, event=event)

    async def _reply_file_via_gateway_or_bridge(self, reply: str, event: AstrMessageEvent) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_file_reply_request(reply))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 file reply 失败，回退本地 Harness: %s", exc)
            return self.harness_bridge.reply_file_ingest_text(reply, event=event)

    async def _get_file_pending_via_gateway_or_bridge(self) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_file_pending_request())
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 file pending 失败，回退本地 Harness: %s", exc)
            return self.harness_bridge.get_file_pending_text()

    async def _get_file_search_via_gateway_or_bridge(self, query: str) -> str:
        try:
            return await self._invoke_gateway_text(build_harness_file_search_request(query))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("后端网关 file search 失败，回退本地 Harness: %s", exc)
            return self.harness_bridge.get_file_search_text(query)

    @staticmethod
    def _categorize_legacy_memory(memory) -> str:
        content = (getattr(memory, "content", "") or "").lower()
        if any(keyword in content for keyword in ["柳州五菱", "五菱", "柳汽东风", "柳汽", "新能源汽车"]):
            return "客户项目优先"
        if any(keyword in content for keyword in ["小红书", "抖音", "微博", "知乎", "平台热点"]):
            return "平台热点优先"
        return "通用记忆"

    def _build_legacy_memory_summary(self, memories) -> list[str]:
        if not memories:
            return []

        categories = collect_unique_labels(memories, self._categorize_legacy_memory)
        return build_category_summary_lines("Legacy 记忆摘要", categories)

    def _build_legacy_memory_followup(self, memory) -> str:
        content = (getattr(memory, "content", "") or "").lower()
        if any(keyword in content for keyword in ["小红书", "抖音", "微博", "知乎"]):
            for label in ["小红书", "抖音", "微博", "知乎"]:
                if label in content:
                    return f"继续跟进 {label} 平台反馈"
        if any(keyword in content for keyword in ["柳州五菱", "五菱", "柳汽东风", "柳汽", "新能源汽车"]):
            for label in ["柳州五菱", "柳汽东风", "新能源汽车"]:
                if label.lower() in content:
                    return f"补充 {label} 最新客户线索"
            return "补充客户项目最新线索"
        return "整理为可复用历史记忆"

    @staticmethod
    def _categorize_legacy_task(task) -> str:
        task_type = getattr(getattr(task, "type", None), "value", "")
        status = getattr(getattr(task, "status", None), "value", "")
        command = str(getattr(task, "payload", {}).get("command", "")).lower()

        if status == "failed":
            return "技术回退"
        if any(keyword in command for keyword in ["五菱", "柳汽", "新能源汽车", "marketing", "campaign"]):
            return "客户洞察"
        if task_type == "local_shell":
            return "执行任务"
        return "通用任务"

    def _build_legacy_task_followup(self, task) -> str:
        category = self._categorize_legacy_task(task)
        if category == "技术回退":
            return "检查任务日志并重新执行"
        if category == "客户洞察":
            return "补充客户关键词和平台维度"
        if category == "执行任务":
            return "确认命令输出并记录结果"
        return "按需继续跟进"

    def _build_legacy_task_summary(self, tasks) -> list[str]:
        if not tasks:
            return []

        categories = collect_unique_labels(tasks, self._categorize_legacy_task)
        lines = build_category_summary_lines("Legacy 任务摘要", categories)
        priority_task = next((task for task in tasks if self._categorize_legacy_task(task) == "技术回退"), None)
        if not priority_task:
            priority_task = tasks[0]
        lines.append(
            build_priority_focus_text(
                self._categorize_legacy_task(priority_task),
                self._build_legacy_task_followup(priority_task),
            )
        )
        lines.append("")
        return lines

    @filter.command("oc2_core")
    async def openclaw_core_help(self, event: AstrMessageEvent):
        help_text = """OpenClaw 企业版 - 常用命令

公司日常只用这 9 个
1. /oc2_request <需求> - 用大白话自动识别到对应简报
2. /oc2_daily_brief <主题> - 获取当天最新信息并生成创意简报
3. /oc2_competitor_brief <品牌> - 获取竞品速览与最新动态
4. /oc2_platform_brief <主题> - 获取平台热点与历史线索
5. /mtoc_hot [主题] - 获取当天热点并生成营销方向
6. /mtoc_news [关键词] - 获取当天新闻并生成营销方案
7. /mtoc_competitor [品牌] - 查看竞品信息与应对策略
8. /oc2_tasks - 查看当前任务与优先关注
9. /oc2_project_context <query> - 查看客户项目上下文

推荐使用顺序
1. 直接用 /oc2_request <需求> 让系统识别任务
2. 也可以手动使用 /oc2_daily_brief、/oc2_competitor_brief、/oc2_platform_brief
3. 再看 /oc2_tasks 确认当前优先处理
4. 最后用 /oc2_project_context <query> 和 /oc2_memory_search <query> 深挖客户与平台线索

管理与查看
- /oc2_status - 查看系统状态
- /oc2_inspection - 查看执行检查
- /oc2_brief_history [daily|competitor|platform] - 查看简报历史
- /oc2_brief_detail <id> - 查看完整简报内容
- /oc2_brief_schedule <type> <topic> [minutes] - 订阅固定简报
- /oc2_file_upload <本地文件路径> - 暂存资料并开始归档选择
- /oc2_file_text <文件名> <内容> - 直接暂存文本资料
- /oc2_file_reply <选择或内容> - 回复当前资料归档步骤
- /oc2_file_search <关键词> - 检索已归档资料
- /oc2_file_pending - 查看待归档资料
- /oc2_memory - 查看记忆总览
- /oc2_async_tasks - 查看异步任务
- /oc2_async_detail <job_id> - 查看异步任务详情
- /oc2_schedules - 查看计划任务
- /oc2_notifications - 查看通知回执

仅研发/管理员使用
- /oc2_async_submit <command>
- /oc2_async_retry <job_id>
- /oc2_async_resume <job_id>
- /oc2_schedule_add <interval_minutes> <command>
- /oc2_flags / /oc2_flags_enable / /oc2_flags_disable
- /oc2_perms / /oc2_perms_add / /oc2_perms_mode
- /oc2_route_debug <text>
- /oc2_task_create <command>
- /oc2_memory_add <content>

更多详情: /oc2_core_about"""
        yield event.plain_result(help_text)

    @filter.command("oc2_core_about")
    async def openclaw_core_about(self, event: AstrMessageEvent):
        about_text = """OpenClaw 企业版作战台

定位
这是给推广服务团队用的客户项目作战台，不是普通聊天机器人。

现阶段最小交付目标
1. 获取当天最新真实信息
2. 基于实时信息产出可直接使用的创意结果

公司日常建议入口
- /oc2_request
- /oc2_daily_brief
- /oc2_competitor_brief
- /oc2_platform_brief
- /mtoc_hot
- /mtoc_news
- /mtoc_competitor
- /oc2_tasks
- /oc2_project_context
- /oc2_memory_search

系统分层
- 前台命令保持简单
- 后台继续由 JW-Claw Harness 执行
- 当前采用 main.py 薄壳入口，核心逻辑收敛在 core/ 与 jw_claw/ 目录

目标方向
新内核，旧皮肤。
先把公司每天真会用的工作流跑顺，再逐步完善平台能力。

当前已接入的资料归档能力
- 可暂存文件或文本资料
- 可按文件类型、归属对象、备注做人工归档
- 当前适合内部资料沉淀和后续检索使用"""
        yield event.plain_result(about_text)

    @filter.command("oc2_status")
    async def show_harness_status(self, event: AstrMessageEvent):
        try:
            yield event.plain_result(self.harness_bridge.get_engine_status_text())
        except Exception as e:
            yield event.plain_result(f"获取 Harness 状态失败: {e}")

    @filter.command("oc2_inspection")
    async def show_inspection_overview(self, event: AstrMessageEvent):
        try:
            yield event.plain_result(self.harness_bridge.get_inspection_overview_text())
        except Exception as e:
            yield event.plain_result(build_error_text("获取 inspection 概览", e))

    @filter.command("oc2_route_debug")
    async def route_debug(self, event: AstrMessageEvent):
        if not is_harness_debug_enabled():
            yield event.plain_result("JW-Claw Harness 调试当前未启用")
            return
        message_text = event.message_str.strip()
        if not message_text:
            yield event.plain_result("请输入要调试的消息，例如: /oc2_route_debug /mt_copy 写一条推广文案")
            return
        try:
            yield event.plain_result(self.harness_bridge.get_route_debug_text(message_text))
        except Exception as e:
            yield event.plain_result(f"路由调试失败: {e}")

    @filter.command("oc2_demo")
    async def run_demo(self, event: AstrMessageEvent):
        demo_text = """OpenClaw 企业版 - 使用示例

公司日常示例
1. /oc2_request 帮我看一下柳州五菱今天的最新动态
   用大白话自动识别成对应简报

2. /oc2_daily_brief 柳州五菱
   获取当天最新信息、客户上下文和创意方向

3. /oc2_competitor_brief 比亚迪
   获取竞品速览、最新动态和下一步建议

4. /oc2_platform_brief 小红书
   获取平台热点、平台动态和历史线索

5. /mtoc_news 柳州五菱
   获取当天新闻并生成营销方案

6. /mtoc_hot 新能源汽车
   获取当天热点并生成传播方向

7. /mtoc_competitor 比亚迪
   查看竞品背景与应对思路

8. /oc2_tasks
   查看当前任务和优先关注

9. /oc2_project_context 柳州五菱
   查看客户项目上下文、最近任务和建议动作

10. /oc2_memory_search 小红书
   搜索平台线索与历史记忆

组合用法
1. 先用 /oc2_request 帮我看一下柳州五菱今天的最新动态
2. 再看 /oc2_tasks 确认当前优先处理
3. 最后用 /oc2_project_context 柳州五菱 和 /oc2_memory_search 小红书 深挖线索

管理查看
- /oc2_status
- /oc2_inspection
- /oc2_brief_history
- /oc2_brief_detail <id>
- /oc2_brief_schedule daily 柳州五菱
- /oc2_async_tasks
- /oc2_schedules
- /oc2_notifications

更多命令: /oc2_core"""
        yield event.plain_result(demo_text)

    @filter.command("oc2_daily_brief")
    async def daily_brief(self, event: AstrMessageEvent):
        query = _strip_self_command_prefix(event.message_str, "oc2_daily_brief")
        if not query:
            yield event.plain_result(build_missing_input_prompt("请输入主题关键词", "/oc2_daily_brief 柳州五菱"))
            return
        try:
            yield event.plain_result(await self._get_daily_brief_via_gateway_or_bridge(query, event))
        except Exception as e:
            yield event.plain_result(build_error_text("获取每日简报", e))

    @filter.command("oc2_request")
    async def request_entry(self, event: AstrMessageEvent):
        request_text = _strip_self_command_prefix(event.message_str, "oc2_request")
        if not request_text:
            yield event.plain_result(build_missing_input_prompt("请输入需求描述", "/oc2_request 帮我看一下柳州五菱今天的最新动态"))
            return
        try:
            yield event.plain_result(await self._get_request_text_via_gateway_or_bridge(request_text, event))
        except Exception as e:
            yield event.plain_result(build_error_text("识别需求", e))

    @filter.command("oc2_competitor_brief")
    async def competitor_brief(self, event: AstrMessageEvent):
        brand = event.message_str.strip()
        if not brand:
            yield event.plain_result(build_missing_input_prompt("请输入竞品品牌", "/oc2_competitor_brief 比亚迪"))
            return
        try:
            yield event.plain_result(await self._get_competitor_brief_via_gateway_or_bridge(brand, event))
        except Exception as e:
            yield event.plain_result(build_error_text("获取竞品简报", e))

    @filter.command("oc2_platform_brief")
    async def platform_brief(self, event: AstrMessageEvent):
        topic = event.message_str.strip()
        if not topic:
            yield event.plain_result(build_missing_input_prompt("请输入平台主题", "/oc2_platform_brief 小红书"))
            return
        try:
            yield event.plain_result(await self._get_platform_brief_via_gateway_or_bridge(topic, event))
        except Exception as e:
            yield event.plain_result(build_error_text("获取平台热点简报", e))

    @filter.command("oc2_brief_history")
    async def brief_history(self, event: AstrMessageEvent):
        kind = event.message_str.strip() or None
        try:
            yield event.plain_result(self.harness_bridge.get_brief_history_text(limit=10, kind=kind))
        except Exception as e:
            yield event.plain_result(build_error_text("获取简报历史", e))

    @filter.command("oc2_brief_detail")
    async def brief_detail(self, event: AstrMessageEvent):
        memory_id = event.message_str.strip()
        if not memory_id:
            yield event.plain_result(build_missing_input_prompt("请输入简报 ID", "/oc2_brief_detail abc123"))
            return
        try:
            yield event.plain_result(self.harness_bridge.get_brief_detail_text(memory_id))
        except Exception as e:
            yield event.plain_result(build_error_text("获取简报详情", e))

    @filter.command("oc2_brief_schedule")
    async def brief_schedule(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split()
        if len(parts) < 2:
            yield event.plain_result(build_missing_input_prompt("请输入简报类型和主题", "/oc2_brief_schedule daily 柳州五菱"))
            return
        kind = parts[0].strip().lower()
        interval_minutes = 1440
        if len(parts) >= 3 and parts[-1].isdigit():
            interval_minutes = int(parts[-1])
            topic = " ".join(parts[1:-1]).strip()
        else:
            topic = " ".join(parts[1:]).strip()
        if not topic:
            yield event.plain_result(build_missing_input_prompt("请输入简报主题", "/oc2_brief_schedule daily 柳州五菱"))
            return
        try:
            yield event.plain_result(
                self.harness_bridge.create_brief_schedule_text(kind, topic, interval_minutes=interval_minutes)
            )
        except Exception as e:
            yield event.plain_result(build_error_text("创建简报订阅", e))

    @filter.command("oc2_file_upload")
    async def file_upload(self, event: AstrMessageEvent):
        file_path = _strip_self_command_prefix(event.message_str, "oc2_file_upload")
        try:
            yield event.plain_result(self.harness_bridge.start_file_ingest_from_path_text(file_path=file_path, event=event))
        except Exception as e:
            yield event.plain_result(build_error_text("暂存资料文件", e))

    @filter.command("oc2_file_text")
    async def file_text(self, event: AstrMessageEvent):
        raw = _strip_self_command_prefix(event.message_str, "oc2_file_text")
        parts = raw.split(" ", 1)
        if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
            yield event.plain_result(build_missing_input_prompt("请输入文件名和内容", "/oc2_file_text 五菱活动复盘.md 这里是复盘内容"))
            return
        try:
            yield event.plain_result(
                await self._start_file_text_via_gateway_or_bridge(parts[0].strip(), parts[1].strip(), event)
            )
        except Exception as e:
            yield event.plain_result(build_error_text("暂存文本资料", e))

    @filter.command("oc2_file_reply")
    async def file_reply(self, event: AstrMessageEvent):
        reply = _strip_self_command_prefix(event.message_str, "oc2_file_reply")
        if not reply:
            yield event.plain_result(build_missing_input_prompt("请输入当前步骤的选择或内容", "/oc2_file_reply A"))
            return
        try:
            yield event.plain_result(await self._reply_file_via_gateway_or_bridge(reply, event))
        except Exception as e:
            yield event.plain_result(build_error_text("处理资料归档回复", e))

    @filter.command("oc2_file_pending")
    async def file_pending(self, event: AstrMessageEvent):
        try:
            yield event.plain_result(await self._get_file_pending_via_gateway_or_bridge())
        except Exception as e:
            yield event.plain_result(build_error_text("查看待归档资料", e))

    @filter.command("oc2_file_search")
    async def file_search(self, event: AstrMessageEvent):
        query = _strip_self_command_prefix(event.message_str, "oc2_file_search")
        if not query:
            yield event.plain_result(build_missing_input_prompt("请输入资料关键词", "/oc2_file_search 柳州五菱"))
            return
        try:
            yield event.plain_result(await self._get_file_search_via_gateway_or_bridge(query))
        except Exception as e:
            yield event.plain_result(build_error_text("检索已归档资料", e))

    @filter.command("oc2_flags")
    async def show_feature_flags(self, event: AstrMessageEvent):
        try:
            status = get_feature_status()
            yield event.plain_result(build_feature_flags_text(status))
        except Exception as e:
            yield event.plain_result(build_error_text("获取功能标志", e))

    @filter.command("oc2_flags_enable")
    async def enable_feature_flag(self, event: AstrMessageEvent):
        flag_name = event.message_str.strip()
        if not flag_name:
            yield event.plain_result(build_feature_toggle_prompt("启用", "/oc2_flags_enable RAGFLOW"))
            return
        try:
            enable_feature(flag_name)
            yield event.plain_result(build_feature_toggled_text(flag_name, enabled=True))
        except Exception as e:
            yield event.plain_result(build_error_text("启用", e))

    @filter.command("oc2_flags_disable")
    async def disable_feature_flag(self, event: AstrMessageEvent):
        flag_name = event.message_str.strip()
        if not flag_name:
            yield event.plain_result(build_feature_toggle_prompt("禁用", "/oc2_flags_disable RAGFLOW"))
            return
        try:
            disable_feature(flag_name)
            yield event.plain_result(build_feature_toggled_text(flag_name, enabled=False))
        except Exception as e:
            yield event.plain_result(build_error_text("禁用", e))

    @filter.command("oc2_perms")
    async def show_permissions(self, event: AstrMessageEvent):
        try:
            rules = self.permission_manager.get_rules()
            mode = self.permission_manager.mode
            yield event.plain_result(build_permissions_text(rules, mode))
        except Exception as e:
            yield event.plain_result(build_error_text("获取权限规则", e))

    @filter.command("oc2_perms_add")
    async def add_permission_rule(self, event: AstrMessageEvent):
        parts = event.message_str.strip().rsplit(maxsplit=1)
        if len(parts) != 2:
            yield event.plain_result(build_usage_text("/oc2_perms_add &lt;pattern&gt; &lt;allow/deny&gt;"))
            return
        pattern, action = parts
        allow = parse_permission_allow(action)
        try:
            self.permission_manager.add_rule(pattern, allow)
            yield event.plain_result(build_permission_added_text(pattern, allow))
        except Exception as e:
            yield event.plain_result(build_error_text("添加权限规则", e))

    @filter.command("oc2_perms_mode")
    async def set_permission_mode(self, event: AstrMessageEvent):
        mode_str = event.message_str.strip().lower()
        mode = resolve_permission_mode(mode_str, PermissionMode)
        if mode is None:
            yield event.plain_result(build_available_modes_text())
            return
        try:
            self.permission_manager.set_mode(mode)
            yield event.plain_result(build_permission_mode_set_text(mode_str))
        except Exception as e:
            yield event.plain_result(build_error_text("设置权限模式", e))

    @filter.command("oc2_tasks")
    async def list_tasks(self, event: AstrMessageEvent):
        try:
            tasks = self.task_manager.list_tasks()
            lines = build_section_lines("任务列表")
            if is_harness_enabled():
                lines.append(self.harness_bridge.get_task_summary_text(limit=10))
                lines.append("")
            lines.extend(build_section_lines("Legacy 任务列表"))
            lines.extend(self._build_legacy_task_summary(tasks))
            lines.extend(
                build_task_lines(
                    tasks,
                    category_getter=self._categorize_legacy_task,
                    followup_getter=self._build_legacy_task_followup,
                )
            )
            yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(build_error_text("获取任务列表", e))

    @filter.command("oc2_async_tasks")
    async def list_async_tasks(self, event: AstrMessageEvent):
        try:
            status = event.message_str.strip() or None
            yield event.plain_result(self.harness_bridge.get_async_job_summary_text(limit=10, status=status))
        except Exception as e:
            yield event.plain_result(build_error_text("获取异步任务列表", e))

    @filter.command("oc2_async_detail")
    async def show_async_task_detail(self, event: AstrMessageEvent):
        job_id = event.message_str.strip()
        if not job_id:
            yield event.plain_result(build_missing_input_prompt("请输入要查看的 Job ID", "/oc2_async_detail abc123"))
            return
        try:
            yield event.plain_result(self.harness_bridge.get_async_job_detail_text(job_id))
        except Exception as e:
            yield event.plain_result(build_error_text("获取异步任务详情", e))

    @filter.command("oc2_async_submit")
    async def submit_async_task(self, event: AstrMessageEvent):
        command_text = _strip_self_command_prefix(event.message_str, "oc2_async_submit")
        if not command_text:
            yield event.plain_result(build_missing_input_prompt("请输入要异步执行的命令", "/oc2_async_submit mtoc_news 柳州五菱"))
            return

        parts = command_text.split(maxsplit=1)
        command_name = parts[0].lstrip("/")
        prompt = parts[1] if len(parts) > 1 else ""
        try:
            text = await self.harness_bridge.submit_async_command_text(command_name, prompt=prompt, event=event)
            yield event.plain_result(text)
        except Exception as e:
            yield event.plain_result(build_error_text("提交异步任务", e))

    @filter.command("oc2_async_retry")
    async def retry_async_task(self, event: AstrMessageEvent):
        job_id = event.message_str.strip()
        if not job_id:
            yield event.plain_result(build_missing_input_prompt("请输入要重试的 Job ID", "/oc2_async_retry abc123"))
            return
        try:
            text = await self.harness_bridge.retry_async_job_text(job_id)
            yield event.plain_result(text)
        except Exception as e:
            yield event.plain_result(build_error_text("重试异步任务", e))

    @filter.command("oc2_async_resume")
    async def resume_async_task(self, event: AstrMessageEvent):
        job_id = event.message_str.strip()
        if not job_id:
            yield event.plain_result(build_missing_input_prompt("请输入要恢复的 Job ID", "/oc2_async_resume abc123"))
            return
        try:
            text = await self.harness_bridge.resume_async_job_text(job_id)
            yield event.plain_result(text)
        except Exception as e:
            yield event.plain_result(build_error_text("恢复异步任务", e))

    @filter.command("oc2_schedules")
    async def list_schedules(self, event: AstrMessageEvent):
        try:
            yield event.plain_result(self.harness_bridge.get_schedule_summary_text(limit=10))
        except Exception as e:
            yield event.plain_result(build_error_text("获取计划任务列表", e))

    @filter.command("oc2_schedule_add")
    async def add_schedule(self, event: AstrMessageEvent):
        parts = event.message_str.strip().split(maxsplit=2)
        if len(parts) < 2:
            yield event.plain_result(build_missing_input_prompt("请输入间隔和命令", "/oc2_schedule_add 60 mtoc_news 柳州五菱"))
            return
        try:
            interval_minutes = int(parts[0])
        except ValueError:
            yield event.plain_result("请输入有效的分钟间隔，例如: /oc2_schedule_add 60 mtoc_news 柳州五菱")
            return
        command_name = parts[1].lstrip("/")
        prompt = parts[2] if len(parts) > 2 else ""
        try:
            yield event.plain_result(self.harness_bridge.create_schedule_text(command_name, prompt=prompt, interval_minutes=interval_minutes))
        except Exception as e:
            yield event.plain_result(build_error_text("创建计划任务", e))

    @filter.command("oc2_notifications")
    async def list_notifications(self, event: AstrMessageEvent):
        try:
            yield event.plain_result(self.harness_bridge.get_notification_summary_text(limit=10))
        except Exception as e:
            yield event.plain_result(build_error_text("获取通知回执", e))

    @filter.command("oc2_task_create")
    async def create_task(self, event: AstrMessageEvent):
        command = event.message_str.strip()
        if not command:
            yield event.plain_result(build_missing_input_prompt("请指定要执行的命令", "/oc2_task_create ls -la"))
            return
        try:
            task_id = self.task_manager.create_task(
                TaskType.LOCAL_SHELL,
                {"command": command}
            )
            yield event.plain_result(build_task_created_text(task_id))
        except Exception as e:
            yield event.plain_result(build_error_text("创建任务", e))

    @filter.command("oc2_memory")
    async def list_memories(self, event: AstrMessageEvent):
        try:
            memories = self.memory_manager.list_memories(limit=20)
            lines = build_section_lines("记忆列表")
            if is_harness_enabled():
                lines.append(self.harness_bridge.get_project_dashboard_text(limit=10))
                lines.append("")
                lines.append(self.harness_bridge.get_memory_summary_text(limit=10))
                lines.append("")
                lines.append(self.harness_bridge.get_context_memory_text(limit=10))
                lines.append("")
                lines.extend(build_section_lines("Legacy 记忆列表"))
                lines.extend(self._build_legacy_memory_summary(memories))
            lines.extend(
                build_memory_lines(
                    memories,
                    category_getter=self._categorize_legacy_memory,
                    followup_getter=self._build_legacy_memory_followup,
                    preview=True,
                )
            )
            yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(build_error_text("获取记忆列表", e))

    @filter.command("oc2_memory_add")
    async def add_memory(self, event: AstrMessageEvent):
        content = event.message_str.strip()
        if not content:
            yield event.plain_result(build_missing_input_prompt("请输入记忆内容", "/oc2_memory_add 这是一条重要的记忆"))
            return
        try:
            harness_memory_id = None
            if is_harness_enabled():
                harness_memory_id = self.harness_bridge.add_memory(
                    content=content,
                    source="astrbot",
                    importance=0.7,
                    metadata={"channel": "oc2_memory_add"},
                )
            memory_id = self.memory_manager.add_memory(
                content=content,
                source="astrbot",
                importance=0.7
            )
            if harness_memory_id:
                yield event.plain_result(
                    f"✅ 已添加记忆\nLegacy ID: {memory_id}\nJW-Claw ID: {harness_memory_id}"
                )
            else:
                yield event.plain_result(build_memory_added_text(memory_id))
        except Exception as e:
            yield event.plain_result(build_error_text("添加记忆", e))

    @filter.command("oc2_memory_search")
    async def search_memory(self, event: AstrMessageEvent):
        query = event.message_str.strip()
        if not query:
            yield event.plain_result(build_missing_input_prompt("请输入搜索关键词", "/oc2_memory_search 重要"))
            return
        try:
            results = self.memory_manager.search_memories(query, limit=5)
            lines = build_section_lines(build_memory_search_header(query))
            if is_harness_enabled():
                lines.append(self.harness_bridge.search_memory_text(query, limit=5))
                lines.append("")
                lines.append(self.harness_bridge.get_context_memory_text(limit=5, query=query))
                lines.append("")
                lines.extend(build_section_lines("Legacy 搜索结果"))
                lines.extend(self._build_legacy_memory_summary(results))
            if not results:
                lines.append(build_memory_search_empty_text())
            else:
                lines.extend(
                    build_memory_lines(
                        results,
                        category_getter=self._categorize_legacy_memory,
                        followup_getter=self._build_legacy_memory_followup,
                    )
                )
            yield event.plain_result("\n".join(lines))
        except Exception as e:
            yield event.plain_result(build_error_text("搜索记忆", e))

    @filter.command("oc2_project_context")
    async def project_context(self, event: AstrMessageEvent):
        query = event.message_str.strip()
        if not query:
            yield event.plain_result(build_project_context_prompt("/oc2_project_context 柳州五菱"))
            return
        try:
            if not is_harness_enabled():
                yield event.plain_result(build_harness_disabled_text("项目上下文"))
                return
            yield event.plain_result(self.harness_bridge.get_project_dashboard_text(limit=10, query=query))
        except Exception as e:
            yield event.plain_result(f"获取项目上下文失败: {e}")
