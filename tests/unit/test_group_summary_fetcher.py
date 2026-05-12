"""W1 / 2A-1 history_fetcher 单测。

覆盖三平台 dispatch 和 normalization：
- aiocqhttp（QQ）：call_action 返回 + 文本提取 + sender_id 过滤
- WebChat：message_history_manager.get + content 解析
- Lark：现成依赖 lark_oapi 模块，测试夹具用 monkeypatch 替身
- 公共：_filter_and_cap（时间窗 + is_bot + max_count 上限）
- 公共：UnsupportedPlatformError 路径
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.group_summary.history_fetcher import (
    UnsupportedPlatformError,
    _filter_and_cap,
    _to_aware,
    fetch_group_messages,
)
from astrbot.core.group_summary.time_range import TimeRange

NOW = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)


def _tr(window_hours: int = 12, max_count: int = 50) -> TimeRange:
    return TimeRange(
        start=NOW - timedelta(hours=window_hours),
        end=NOW,
        max_count=max_count,
        description=f"最近 {window_hours}h",
    )


def _msg(content="hi", ts=None, is_bot=False, sender="u1", sender_id="u1"):
    return {
        "sender": sender,
        "sender_id": sender_id,
        "content": content,
        "timestamp": ts or NOW,
        "is_bot": is_bot,
    }


# ── _to_aware ────────────────────────────────────────────────────────────────


def test_to_aware_datetime_pass_through():
    assert _to_aware(NOW) == NOW


def test_to_aware_naive_datetime_gets_utc():
    naive = datetime(2026, 5, 12, 12, 0, 0)
    result = _to_aware(naive)
    assert result.tzinfo is not None


def test_to_aware_unix_seconds():
    ts = int(NOW.timestamp())
    assert _to_aware(ts).timestamp() == ts


def test_to_aware_unix_millis():
    ts_ms = int(NOW.timestamp() * 1000)
    result = _to_aware(ts_ms)
    assert abs(result.timestamp() - NOW.timestamp()) < 1


def test_to_aware_iso_string():
    iso = "2026-05-12T12:00:00Z"
    result = _to_aware(iso)
    assert result is not None
    assert result.hour == 12


def test_to_aware_garbage_returns_none():
    assert _to_aware("not-a-timestamp") is None
    assert _to_aware(None) is None


# ── _filter_and_cap ──────────────────────────────────────────────────────────


def test_filter_drops_bots():
    msgs = [_msg(content="a", is_bot=False), _msg(content="b", is_bot=True)]
    kept = _filter_and_cap(msgs, _tr())
    assert len(kept) == 1
    assert kept[0]["content"] == "a"


def test_filter_drops_out_of_window():
    msgs = [
        _msg(content="too_old", ts=NOW - timedelta(hours=20)),
        _msg(content="in_window", ts=NOW - timedelta(hours=1)),
    ]
    kept = _filter_and_cap(msgs, _tr(window_hours=12))
    assert len(kept) == 1
    assert kept[0]["content"] == "in_window"


def test_filter_caps_to_max_count_keep_tail():
    msgs = [
        _msg(content=f"m{i}", ts=NOW - timedelta(minutes=60 - i)) for i in range(60)
    ]
    kept = _filter_and_cap(msgs, _tr(max_count=10))
    assert len(kept) == 10
    # 保留最新 10 条
    contents = [m["content"] for m in kept]
    assert "m59" in contents
    assert "m0" not in contents


def test_filter_sorts_ascending():
    msgs = [
        _msg(content="b", ts=NOW - timedelta(minutes=2)),
        _msg(content="a", ts=NOW - timedelta(minutes=5)),
        _msg(content="c", ts=NOW - timedelta(minutes=1)),
    ]
    kept = _filter_and_cap(msgs, _tr())
    assert [m["content"] for m in kept] == ["a", "b", "c"]


# ── aiocqhttp branch ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_qq_normalizes_call_action_response():
    bot = MagicMock()
    bot.call_action = AsyncMock(
        return_value={
            "messages": [
                {
                    "message_id": "1001",
                    "time": int(NOW.timestamp()) - 60,
                    "sender": {"user_id": "111", "nickname": "张三"},
                    "message": [
                        {"type": "text", "data": {"text": "客户希望加快"}},
                    ],
                },
                {
                    "message_id": "1002",
                    "time": int(NOW.timestamp()) - 30,
                    "sender": {"user_id": "222", "nickname": "李四"},
                    "message": "周三前出方案",
                },
            ]
        }
    )

    platform_inst = MagicMock()
    platform_inst.bot = bot

    event = MagicMock()
    event.message_obj = MagicMock()
    event.message_obj.group_id = "1234"
    event.message_obj.message_id = "9999"  # 不在历史里
    event.get_platform_id.return_value = "qqbot"
    event.unified_msg_origin = "qqbot:GroupMessage:1234_111"

    out = await fetch_group_messages(
        platform_inst=platform_inst,
        message_history_manager=MagicMock(),
        event=event,
        time_range=_tr(),
    )
    assert len(out) == 2
    assert out[0]["sender"] == "张三"
    assert "加快" in out[0]["content"]
    assert out[1]["content"] == "周三前出方案"


@pytest.mark.asyncio
async def test_fetch_qq_skips_self_bot_and_trigger():
    bot = MagicMock()
    bot.call_action = AsyncMock(
        return_value={
            "messages": [
                {
                    "message_id": "trigger",
                    "time": int(NOW.timestamp()) - 60,
                    "sender": {"user_id": "111", "nickname": "张三"},
                    "message": "@DC-Agent 总结",
                },
                {
                    "message_id": "real",
                    "time": int(NOW.timestamp()) - 30,
                    "sender": {"user_id": "bot1", "nickname": "DC-Agent"},
                    "message": "好的",
                },
                {
                    "message_id": "good",
                    "time": int(NOW.timestamp()) - 10,
                    "sender": {"user_id": "222", "nickname": "李四"},
                    "message": "真的吗",
                },
            ]
        }
    )
    platform_inst = MagicMock()
    platform_inst.bot = bot

    event = MagicMock()
    event.message_obj = MagicMock()
    event.message_obj.group_id = "1234"
    event.message_obj.message_id = "trigger"
    event.get_platform_id.return_value = "qqbot"
    event.unified_msg_origin = "qqbot:GroupMessage:1234_111"

    out = await fetch_group_messages(
        platform_inst=platform_inst,
        message_history_manager=MagicMock(),
        event=event,
        time_range=_tr(),
        self_bot_id="bot1",
    )
    # trigger 跳过 + bot 自己的也跳 → 只剩 "good"
    assert len(out) == 1
    assert out[0]["content"] == "真的吗"


@pytest.mark.asyncio
async def test_fetch_qq_call_action_fails_raises_unsupported():
    bot = MagicMock()
    bot.call_action = AsyncMock(side_effect=RuntimeError("API down"))
    platform_inst = MagicMock()
    platform_inst.bot = bot

    event = MagicMock()
    event.message_obj = MagicMock()
    event.message_obj.group_id = "1234"
    event.message_obj.message_id = "x"
    event.get_platform_id.return_value = "qqbot"
    event.unified_msg_origin = "qqbot:GroupMessage:1234_111"

    with pytest.raises(UnsupportedPlatformError):
        await fetch_group_messages(
            platform_inst=platform_inst,
            message_history_manager=MagicMock(),
            event=event,
            time_range=_tr(),
        )


# ── WebChat branch ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_webchat_normalizes_records():
    rec1 = MagicMock()
    rec1.id = "1"
    rec1.sender_id = "u1"
    rec1.sender_name = "Alice"
    rec1.content = {"text": "hello"}
    rec1.created_at = NOW - timedelta(minutes=5)

    rec2 = MagicMock()
    rec2.id = "2"
    rec2.sender_id = "u2"
    rec2.sender_name = "Bob"
    rec2.content = "plain string"
    rec2.created_at = NOW - timedelta(minutes=3)

    mgr = MagicMock()
    mgr.get = AsyncMock(return_value=[rec1, rec2])

    # 没 bot 属性 + 没 lark_api 属性 → 走 webchat 分支
    platform_inst = MagicMock(spec=[])

    event = MagicMock()
    event.message_obj = MagicMock()
    event.message_obj.message_id = "trigger"
    event.message_obj.group_id = None
    event.get_platform_id.return_value = "webchat"
    event.unified_msg_origin = "webchat:Friend:conv-abc"

    out = await fetch_group_messages(
        platform_inst=platform_inst,
        message_history_manager=mgr,
        event=event,
        time_range=_tr(),
    )
    assert len(out) == 2
    assert out[0]["content"] == "hello"
    assert out[1]["content"] == "plain string"


@pytest.mark.asyncio
async def test_fetch_webchat_get_fails_raises_unsupported():
    mgr = MagicMock()
    mgr.get = AsyncMock(side_effect=RuntimeError("db down"))
    platform_inst = MagicMock(spec=[])  # 都不匹配 → webchat fallback

    event = MagicMock()
    event.message_obj = MagicMock()
    event.message_obj.message_id = "trigger"
    event.message_obj.group_id = None
    event.get_platform_id.return_value = "webchat"
    event.unified_msg_origin = "webchat:Friend:conv-abc"

    with pytest.raises(UnsupportedPlatformError):
        await fetch_group_messages(
            platform_inst=platform_inst,
            message_history_manager=mgr,
            event=event,
            time_range=_tr(),
        )
