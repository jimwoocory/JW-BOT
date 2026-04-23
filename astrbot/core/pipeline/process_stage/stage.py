from collections.abc import AsyncGenerator

from astrbot.core import logger
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.provider.entities import ProviderRequest
from astrbot.core.star.star_handler import StarHandlerMetadata

from ..context import PipelineContext
from ..stage import Stage, register_stage
from .method.agent_request import AgentRequestSubStage
from .method.star_request import StarRequestSubStage
from .router_stage import RouterStage


@register_stage
class ProcessStage(Stage):
    async def initialize(self, ctx: PipelineContext) -> None:
        self.ctx = ctx
        self.config = ctx.astrbot_config
        self.plugin_manager = ctx.plugin_manager

        # initialize agent sub stage
        self.agent_sub_stage = AgentRequestSubStage()
        await self.agent_sub_stage.initialize(ctx)

        # initialize star request sub stage
        self.star_request_sub_stage = StarRequestSubStage()
        await self.star_request_sub_stage.initialize(ctx)

        self.router_stage = RouterStage()
        await self.router_stage.initialize(ctx)

    async def process(
        self,
        event: AstrMessageEvent,
    ) -> None | AsyncGenerator[None, None]:
        """处理事件"""
        router_handled = False
        try:
            router_handled = await self.router_stage.route(event)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Router stage failed, fallback to existing pipeline: %s",
                exc,
            )

        activated_handlers: list[StarHandlerMetadata] = event.get_extra(
            "activated_handlers",
        )
        # 有插件 Handler 被激活
        if activated_handlers:
            try:
                async for resp in self.star_request_sub_stage.process(event):
                    # 生成器返回值处理
                    if isinstance(resp, ProviderRequest):
                        # Handler 的 LLM 请求
                        event.set_extra("provider_request", resp)
                        self.router_stage.restore_event_message(event)
                        _t = False
                        async for _ in self.agent_sub_stage.process(event):
                            _t = True
                            yield
                        if not _t:
                            yield
                    else:
                        yield
            finally:
                self.router_stage.restore_event_message(event)

        if router_handled:
            yield
            return

        # 调用 LLM 相关请求
        if not self.ctx.astrbot_config["provider_settings"].get("enable", True):
            return

        if (
            not event._has_send_oper
            and event.is_at_or_wake_command
            and not event.call_llm
        ):
            # 是否有过发送操作 and 是否是被 @ 或者通过唤醒前缀
            if (
                event.get_result() and not event.is_stopped()
            ) or not event.get_result():
                async for _ in self.agent_sub_stage.process(event):
                    yield
