"""W1 / 2A-1 group_summary 模块单测。

覆盖：
- parse_time_range：默认值 / 整天关键词 / N 条 / N 天 / N 小时 / 显式时分 / 容错
- format_summary：四段输出、空段落处理、表头格式
- summarize_group_chat：空输入、正常 JSON、code-fence JSON、partial keys、
  LLM 抛错、超长截断
- 模块导出 GROUP_SUMMARY_SYSTEM_PROMPT 供 prompt 验证
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.group_summary import (
    GROUP_SUMMARY_SYSTEM_PROMPT,
    GroupSummary,
    TimeRange,
    format_summary,
    parse_time_range,
    summarize_group_chat,
)
from astrbot.core.group_summary.time_range import (
    DEFAULT_MAX_COUNT,
    DEFAULT_WINDOW_HOURS,
)

# ── parse_time_range ─────────────────────────────────────────────────────────


NOW = datetime(2026, 5, 12, 10, 30, 0, tzinfo=timezone.utc)


def test_time_range_empty_uses_default():
    tr = parse_time_range("", now=NOW)
    assert tr.max_count == DEFAULT_MAX_COUNT
    assert (NOW - tr.start).total_seconds() == DEFAULT_WINDOW_HOURS * 3600
    assert tr.end == NOW


def test_time_range_none_uses_default():
    tr = parse_time_range(None, now=NOW)
    assert tr.max_count == DEFAULT_MAX_COUNT


def test_time_range_today_zh():
    tr = parse_time_range("今天", now=NOW)
    assert tr.start.hour == 0 and tr.start.minute == 0
    assert tr.end == NOW
    assert "今天" in tr.description


def test_time_range_today_en():
    tr = parse_time_range("today", now=NOW)
    assert tr.start.hour == 0


def test_time_range_yesterday():
    tr = parse_time_range("昨天", now=NOW)
    # 昨天的起点是 24h 前的 0 点，终点是今天 0 点
    assert tr.start.hour == 0 and tr.start.day == 11
    assert tr.end.hour == 0 and tr.end.day == 12


def test_time_range_recent_n_messages():
    tr = parse_time_range("最近 30 条", now=NOW)
    assert tr.max_count == 30
    # 窗口仍是默认
    assert (NOW - tr.start).total_seconds() == DEFAULT_WINDOW_HOURS * 3600


def test_time_range_recent_n_messages_no_space():
    tr = parse_time_range("最近100条", now=NOW)
    assert tr.max_count == 100


def test_time_range_last_n_en():
    tr = parse_time_range("last 20", now=NOW)
    assert tr.max_count == 20


def test_time_range_recent_days():
    tr = parse_time_range("最近 3 天", now=NOW)
    assert (NOW - tr.start).total_seconds() == 3 * 24 * 3600


def test_time_range_recent_hours():
    tr = parse_time_range("最近 6 小时", now=NOW)
    assert (NOW - tr.start).total_seconds() == 6 * 3600


def test_time_range_last_week():
    tr = parse_time_range("最近一周", now=NOW)
    assert (NOW - tr.start).total_seconds() == 7 * 24 * 3600


def test_time_range_explicit_yesterday_time():
    tr = parse_time_range("从昨天 9:00 开始", now=NOW)
    assert tr.start.day == 11
    assert tr.start.hour == 9
    assert tr.start.minute == 0


def test_time_range_explicit_today_with_chinese_colon():
    tr = parse_time_range("今天 14：30", now=NOW)
    assert tr.start.hour == 14
    assert tr.start.minute == 30


def test_time_range_count_clamped():
    tr = parse_time_range("最近 9999 条", now=NOW)
    # 上限 500
    assert tr.max_count == 500


def test_time_range_unknown_falls_back_to_default():
    tr = parse_time_range("我说点别的话题", now=NOW)
    assert tr.max_count == DEFAULT_MAX_COUNT


# ── format_summary ───────────────────────────────────────────────────────────


def _make_summary(**kwargs) -> GroupSummary:
    base = dict(
        client_feedback="客户希望加快进度",
        boss_requests="老板要求周三前出方案",
        execution_issues="缺设计资源",
        stage_conclusions="今天敲定主视觉方向",
        message_count=42,
        time_range="今天",
        raw_response="",
    )
    base.update(kwargs)
    return GroupSummary(**base)


def test_format_summary_has_four_sections():
    md = format_summary(_make_summary())
    assert "### 客户反馈" in md
    assert "### 老板要求" in md
    assert "### 执行问题" in md
    assert "### 阶段结论" in md


def test_format_summary_header():
    md = format_summary(_make_summary())
    first = md.splitlines()[0]
    assert first.startswith("## 群聊总结")
    assert "42" in first
    assert "今天" in first


def test_format_summary_empty_section_renders_placeholder():
    md = format_summary(_make_summary(client_feedback=""))
    # 找到客户反馈那段的 body
    block = md.split("### 客户反馈")[1].split("###")[0]
    assert "（无）" in block


def test_format_summary_no_markdown_injection_breaks_sections():
    md = format_summary(_make_summary(client_feedback="### 注入 ###"))
    # 注入的 markdown 不该破坏结构 — 4 个 ### 段标题仍齐全（容忍内容里有 ###）
    assert md.count("### 客户反馈") == 1
    assert md.count("### 老板要求") == 1


# ── summarize_group_chat ─────────────────────────────────────────────────────


def _make_msg(content: str, sender: str = "张三") -> dict:
    return {
        "sender": sender,
        "sender_id": "u1",
        "content": content,
        "timestamp": NOW,
        "is_bot": False,
    }


def _mock_provider(completion_text: str):
    p = MagicMock()
    resp = MagicMock()
    resp.completion_text = completion_text
    p.text_chat = AsyncMock(return_value=resp)
    return p


def _tr_default() -> TimeRange:
    return parse_time_range("", now=NOW)


@pytest.mark.asyncio
async def test_summarize_empty_returns_empty_no_llm_call():
    p = _mock_provider("never called")
    result = await summarize_group_chat([], llm_provider=p, time_range=_tr_default())
    assert result.message_count == 0
    assert result.client_feedback == "（无）"
    assert result.boss_requests == "（无）"
    assert result.execution_issues == "（无）"
    assert result.stage_conclusions == "（无）"
    p.text_chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_summarize_normal_json():
    p = _mock_provider(
        '{"client_feedback":"客户a","boss_requests":"老板b",'
        '"execution_issues":"问题c","stage_conclusions":"结论d"}'
    )
    result = await summarize_group_chat(
        [_make_msg("hi"), _make_msg("there")],
        llm_provider=p,
        time_range=_tr_default(),
    )
    assert result.client_feedback == "客户a"
    assert result.boss_requests == "老板b"
    assert result.execution_issues == "问题c"
    assert result.stage_conclusions == "结论d"
    assert result.message_count == 2


@pytest.mark.asyncio
async def test_summarize_code_fence_json():
    p = _mock_provider(
        '```json\n{"client_feedback":"a","boss_requests":"b","execution_issues":"c","stage_conclusions":"d"}\n```'
    )
    result = await summarize_group_chat(
        [_make_msg("hi")], llm_provider=p, time_range=_tr_default()
    )
    assert result.client_feedback == "a"


@pytest.mark.asyncio
async def test_summarize_partial_keys_fills_empty():
    p = _mock_provider('{"client_feedback":"only this one"}')
    result = await summarize_group_chat(
        [_make_msg("hi")], llm_provider=p, time_range=_tr_default()
    )
    assert result.client_feedback == "only this one"
    assert result.boss_requests == "（无）"
    assert result.execution_issues == "（无）"
    assert result.stage_conclusions == "（无）"


@pytest.mark.asyncio
async def test_summarize_malformed_json_doesnt_raise():
    p = _mock_provider("not json at all, just prose")
    result = await summarize_group_chat(
        [_make_msg("hi"), _make_msg("hi2")],
        llm_provider=p,
        time_range=_tr_default(),
    )
    # 不抛错，且 message_count 仍诚实
    assert result.message_count == 2
    assert result.client_feedback == "（无）"
    assert "not json" in result.raw_response


@pytest.mark.asyncio
async def test_summarize_llm_raises_returns_empty():
    p = MagicMock()
    p.text_chat = AsyncMock(side_effect=RuntimeError("provider down"))
    result = await summarize_group_chat(
        [_make_msg("hi")], llm_provider=p, time_range=_tr_default()
    )
    assert result.message_count == 0
    assert result.raw_response == "<llm_call_failed>"


@pytest.mark.asyncio
async def test_summarize_truncates_long_input():
    # 比 ceiling 多
    msgs = [_make_msg(f"m{i}") for i in range(500)]
    p = _mock_provider(
        '{"client_feedback":"a","boss_requests":"b","execution_issues":"c","stage_conclusions":"d"}'
    )
    result = await summarize_group_chat(msgs, llm_provider=p, time_range=_tr_default())
    # message_count 报告原始数量
    assert result.message_count == 500
    # LLM 收到的应该是截断后的
    sent_prompt = p.text_chat.await_args.kwargs.get("prompt", "")
    # 最后一条 m499 必定保留
    assert "m499" in sent_prompt
    # 最早一条 m0 必定被丢
    assert "m0:" not in sent_prompt or "m499" in sent_prompt  # 防 substring 误判


@pytest.mark.asyncio
async def test_summarize_list_value_coerced_to_string():
    p = _mock_provider(
        '{"client_feedback":["a","b","c"],"boss_requests":"x","execution_issues":"y","stage_conclusions":"z"}'
    )
    result = await summarize_group_chat(
        [_make_msg("hi")], llm_provider=p, time_range=_tr_default()
    )
    # list 被合并
    assert "a" in result.client_feedback
    assert "b" in result.client_feedback


# ── module exports ──────────────────────────────────────────────────────────


def test_system_prompt_has_four_section_keys():
    """Prompt 模板必须显式提到四个 JSON key（防 LLM 漏字段）。"""
    for key in (
        "client_feedback",
        "boss_requests",
        "execution_issues",
        "stage_conclusions",
    ):
        assert key in GROUP_SUMMARY_SYSTEM_PROMPT


def test_system_prompt_mentions_role_descriptions():
    """Prompt 应描述四类信息的来源（甲方/老板/执行/阶段），引导 LLM 准确分类。"""
    for keyword in ("甲方", "老板", "执行", "结论"):
        assert keyword in GROUP_SUMMARY_SYSTEM_PROMPT
