import logging
import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

from data.plugins.openclaw_connector.gateway_contract import (
    GatewayRequestSpec,
    build_harness_daily_brief_request,
    build_harness_request_request,
)
from data.plugins.openclaw_connector.settings import load_connector_settings
from jw_astrbot_shell import (
    HarnessAstrBotBridge,
    is_frontend_local_fallback_enabled,
    is_harness_enabled,
)

logger = logging.getLogger("openclaw.plugins.openclaw_briefing")


def _strip_self_command_prefix(raw_text: str, command_name: str) -> str:
    text = (raw_text or "").strip()
    for prefix in (f"/{command_name}", command_name):
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            return text[len(prefix):].strip()
    return text


@star.register("openclaw_briefing", "OpenClaw Team", "OpenClaw 干净业务输出插件", "0.1.0")
class OpenClawBriefingPlugin(star.Star):
    def __init__(self, context):
        super().__init__(context)
        self.harness_bridge = HarnessAstrBotBridge()
        gateway_settings = load_connector_settings()
        self.gateway_api_url = gateway_settings["api_url"]
        self.gateway_api_token = gateway_settings["api_token"]
        self.gateway_timeout = int(gateway_settings["timeout"])
        logger.info("业务简报插件加载成功")

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

    @filter.command("brief_help")
    async def help(self, event: AstrMessageEvent):
        yield event.plain_result(
            "OpenClaw 业务简报（兼容入口）\n\n"
            "/brief_request <需求> - 兼容旧入口，内部转到 Harness 简报主线\n"
            "/brief_daily <主题> - 兼容旧入口，内部转到 Harness 简报主线\n\n"
            "推荐后续统一使用：\n"
            "1. /oc2_request <需求>\n"
            "2. /oc2_daily_brief <主题>\n"
            "说明：\n"
            "• 本插件仅保留旧命令兼容\n"
            "• 实际业务结果由 Harness 主线生成"
        )

    @filter.command("brief_request")
    async def request_entry(self, event: AstrMessageEvent):
        request_text = _strip_self_command_prefix(event.message_str, "brief_request")
        if not request_text:
            yield event.plain_result("请输入需求，例如: /brief_request 帮我看一下柳州五菱今天的最新动态")
            return
        if not is_harness_enabled():
            yield event.plain_result("【业务简报】系统当前未启用 Harness，无法生成实时简报。")
            return
        try:
            text = await self._invoke_gateway_text(build_harness_request_request(request_text))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("brief_request 后端网关失败，回退本地 Harness: %s", exc)
            text = await self.harness_bridge.get_request_text(request_text, event=event)
        yield event.plain_result(text)

    @filter.command("brief_daily")
    async def daily(self, event: AstrMessageEvent):
        topic = _strip_self_command_prefix(event.message_str, "brief_daily")
        if not topic:
            yield event.plain_result("请输入主题，例如: /brief_daily 柳州五菱")
            return
        if not is_harness_enabled():
            yield event.plain_result("【业务简报】系统当前未启用 Harness，无法生成实时简报。")
            return
        try:
            text = await self._invoke_gateway_text(build_harness_daily_brief_request(topic))
        except Exception as exc:
            if not is_frontend_local_fallback_enabled():
                raise
            logger.warning("brief_daily 后端网关失败，回退本地 Harness: %s", exc)
            text = await self.harness_bridge.get_daily_brief_text(topic, event=event)
        yield event.plain_result(text)
