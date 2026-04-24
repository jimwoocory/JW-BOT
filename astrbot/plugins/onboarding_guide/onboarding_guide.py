"""
新员工引导插件

首次对话时通过 ABC 选择引导员工完成角色配置，自动绑定对应人格。
完成后进入正常模式，不再拦截消息。
"""

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageEventResult
from astrbot.api.message_components import Plain
from astrbot.api.star import Star, register
from astrbot.core import sp

_WELCOME = """\
👋 你好！我是你的智能工作助手。

在开始之前，请告诉我你主要负责什么工作？

请回复字母选择：
  A — 推广 / 运营 / 内容
  B — 项目管理 / 跟进
  C — 技术 / 运维\
"""

_CONFIRM = {
    "A": (
        "Biz_Assistant_Claw",
        "推广运营助手",
        "你现在可以直接描述营销需求，我来帮你制定方案、撰写文案、规划投放策略。\n\n试试发：「帮我做一个五一社交媒体推广方案」",
    ),
    "B": (
        "Enterprise_Ops_Kernel",
        "项目跟进助手",
        "你现在可以直接描述项目进展或审批需求，我来帮你整理跟进、起草汇报、发起审批流程。\n\n试试发：「我需要跟进本周推广项目的进度」",
    ),
    "C": (
        "DevOps_Console",
        "技术运维助手",
        "你现在可以直接描述技术问题或运维需求，我来帮你排查、规划和处理。\n\n试试发：「帮我检查一下服务器状态」",
    ),
}

_INVALID = "请回复 A、B 或 C 中的一个字母来完成选择。"

_SP_KEY_STATE = "onboarding_state"
_SP_KEY_SESSION = "session_service_config"
_STATE_SELECTING = "selecting_role"
_STATE_DONE = "completed"


@register(
    "onboarding_guide",
    "onboarding_guide",
    "新员工引导 - ABC 角色选择与人格自动绑定",
    "1.0.0",
)
class OnboardingGuidePlugin(Star):
    async def on_message(self, event: AstrMessageEvent) -> None:
        umo = event.unified_msg_origin

        state = await sp.get_async(
            scope="umo",
            scope_id=umo,
            key=_SP_KEY_STATE,
            default=None,
        )

        # 已完成引导，让正常 pipeline 处理
        if state == _STATE_DONE:
            return

        text = (event.message_str or "").strip().upper()

        if state is None:
            # 第一次对话：进入选择角色步骤
            await sp.put_async(
                scope="umo",
                scope_id=umo,
                key=_SP_KEY_STATE,
                value=_STATE_SELECTING,
            )
            self._reply(event, _WELCOME)
            return

        if state == _STATE_SELECTING:
            if text in _CONFIRM:
                persona_id, role_name, hint = _CONFIRM[text]
                await self._bind_persona(umo, persona_id)
                await sp.put_async(
                    scope="umo",
                    scope_id=umo,
                    key=_SP_KEY_STATE,
                    value=_STATE_DONE,
                )
                msg = f"✅ 已为你配置「{role_name}」。\n\n{hint}"
                logger.info(
                    "[Onboarding] %s 完成引导，角色=%s persona=%s",
                    umo,
                    role_name,
                    persona_id,
                )
                self._reply(event, msg)
            else:
                self._reply(event, _INVALID)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _reply(self, event: AstrMessageEvent, text: str) -> None:
        event.set_result(MessageEventResult().message(text).use_t2i(False))
        # 阻止后续 LLM 处理这条消息
        event.should_call_llm(True)

    async def _bind_persona(self, umo: str, persona_id: str) -> None:
        session_config = (
            await sp.get_async(
                scope="umo",
                scope_id=umo,
                key=_SP_KEY_SESSION,
                default={},
            )
            or {}
        )
        session_config["persona_id"] = persona_id
        await sp.put_async(
            scope="umo",
            scope_id=umo,
            key=_SP_KEY_SESSION,
            value=session_config,
        )
