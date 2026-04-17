import logging
import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

from data.plugins.openclaw_connector.gateway_contract import (
    GatewayRequestSpec,
    build_harness_file_pending_request,
    build_harness_file_reply_request,
    build_harness_file_search_request,
    build_harness_file_text_request,
)
from data.plugins.openclaw_connector.settings import load_connector_settings
from harness_layer.config import DEFAULT_CONFIG, HarnessConfig
from harness_layer.knowledge_ingest import KnowledgeIngestService
from jw_claw.astrbot import HarnessAstrBotBridge, is_frontend_local_fallback_enabled

logger = logging.getLogger("openclaw.plugins.openclaw_knowledge_ingest")


@star.register("openclaw_knowledge_ingest", "OpenClaw Team", "OpenClaw 资料上传入库插件", "0.1.0")
class OpenClawKnowledgeIngestPlugin(star.Star):
    def __init__(self, context):
        super().__init__(context)
        self.ingest = KnowledgeIngestService(DEFAULT_CONFIG)
        self.harness_bridge = HarnessAstrBotBridge()
        gateway_settings = load_connector_settings()
        self.gateway_api_url = gateway_settings["api_url"]
        self.gateway_api_token = gateway_settings["api_token"]
        self.gateway_timeout = int(gateway_settings["timeout"])
        logger.info("资料上传入库插件加载成功")

    @staticmethod
    def _bridge_text_to_kb_text(text: str) -> str:
        return (
            (text or "")
            .replace("/oc2_file_upload", "/kb_upload")
            .replace("/oc2_file_text", "/kb_text")
            .replace("/oc2_file_reply", "/kb_reply")
            .replace("/oc2_file_pending", "/kb_pending")
            .replace("/oc2_file_search", "/kb_search")
        )

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
                    raise RuntimeError(f"HTTP {resp.status}: {await resp.text()}")
                data = await resp.json()
        result = data.get("reply") or data.get("text")
        if not result:
            raise RuntimeError("未返回结果")
        return str(result)

    @filter.command("kb_help")
    async def help(self, event: AstrMessageEvent):
        yield event.plain_result(
            "OpenClaw 资料入库（兼容入口）\n\n"
            "/kb_upload <本地文件路径> - 兼容旧入口，内部转到 Harness 资料归档\n"
            "/kb_text <文件名> <内容> - 兼容旧入口，内部转到 Harness 资料归档\n"
            "/kb_reply <选择或内容> - 回复当前资料归档步骤\n"
            "/kb_pending - 查看待确认资料\n"
            "/kb_confirm <upload_id> <category> [brand] - 兼容旧确认方式\n"
            "/kb_search <关键词> - 检索已归档资料\n\n"
            "推荐后续统一使用：/oc2_file_*"
        )

    @filter.command("kb_upload")
    async def upload(self, event: AstrMessageEvent):
        raw = self._strip_command(event.message_str, "kb_upload")
        if not raw:
            yield event.plain_result("请输入本地文件路径，例如: /kb_upload /Users/dianchi/Desktop/五菱品牌规范.md")
            return
        yield event.plain_result(
            self._bridge_text_to_kb_text(
                self.harness_bridge.start_file_ingest_from_path_text(raw, event=event)
            )
        )

    @filter.command("kb_text")
    async def upload_text(self, event: AstrMessageEvent):
        raw = self._strip_command(event.message_str, "kb_text")
        parts = raw.split(" ", 1)
        if len(parts) < 2:
            yield event.plain_result("请输入文件名和内容，例如: /kb_text 五菱活动复盘.md 这里是复盘内容")
            return

        filename, content = parts[0].strip(), parts[1].strip()
        if not content:
            yield event.plain_result("资料内容不能为空。")
            return

        try:
            text = await self._invoke_gateway_text(build_harness_file_text_request(filename, content))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("kb_text 后端网关失败，回退本地 Harness: %s", exc)
            text = self.harness_bridge.start_file_ingest_from_text(filename, content, event=event)
        yield event.plain_result(self._bridge_text_to_kb_text(text))

    @filter.command("kb_pending")
    async def pending(self, event: AstrMessageEvent):
        try:
            text = await self._invoke_gateway_text(build_harness_file_pending_request())
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("kb_pending 后端网关失败，回退本地 Harness: %s", exc)
            text = self.harness_bridge.get_file_pending_text()
        yield event.plain_result(self._bridge_text_to_kb_text(text))

    @filter.command("kb_reply")
    async def reply(self, event: AstrMessageEvent):
        reply_text = self._strip_command(event.message_str, "kb_reply")
        if not reply_text:
            yield event.plain_result("请输入当前步骤的选择或内容，例如: /kb_reply A")
            return
        try:
            text = await self._invoke_gateway_text(build_harness_file_reply_request(reply_text))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("kb_reply 后端网关失败，回退本地 Harness: %s", exc)
            text = self.harness_bridge.reply_file_ingest_text(reply_text, event=event)
        yield event.plain_result(self._bridge_text_to_kb_text(text))

    @filter.command("kb_confirm")
    async def confirm(self, event: AstrMessageEvent):
        raw = self._strip_command(event.message_str, "kb_confirm")
        parts = [part for part in raw.split() if part]
        if len(parts) < 2:
            yield event.plain_result("请输入 upload_id 和 category，例如: /kb_confirm ab12cd34 past_copywriting 柳州五菱")
            return

        upload_id, category = parts[0], parts[1]
        brand = " ".join(parts[2:]).strip() if len(parts) > 2 else None
        try:
            result = self.ingest.confirm(upload_id, category, brand)
        except FileNotFoundError:
            yield event.plain_result("未找到待确认资料，请先执行 /kb_pending 查看。")
            return
        except ValueError:
            yield event.plain_result("资料类型无效。\n\n" + self.ingest.categories_text())
            return
        except Exception as exc:
            yield event.plain_result(f"入库失败: {exc}")
            return

        yield event.plain_result(
            "已入库\n"
            f"- 品牌: {result.get('brand', 'general')}\n"
            f"- 类型: {result.get('category', '')}\n"
            f"- 文件: {result.get('source_name', '')}\n"
            f"- 位置: {result.get('final_path', '')}"
        )

    @filter.command("kb_search")
    async def search(self, event: AstrMessageEvent):
        query = self._strip_command(event.message_str, "kb_search")
        if not query:
            yield event.plain_result("请输入资料关键词，例如: /kb_search 柳州五菱")
            return
        try:
            text = await self._invoke_gateway_text(build_harness_file_search_request(query))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("kb_search 后端网关失败，回退本地 Harness: %s", exc)
            text = self.harness_bridge.get_file_search_text(query)
        yield event.plain_result(self._bridge_text_to_kb_text(text))

    @staticmethod
    def _strip_command(raw_text: str, command_name: str) -> str:
        text = (raw_text or "").strip()
        for prefix in (f"/{command_name}", command_name):
            if text == prefix:
                return ""
            if text.startswith(prefix + " "):
                return text[len(prefix):].strip()
        return text
