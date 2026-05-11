"""单测：astrbot/core/router_decision_logger.py

覆盖：
- 基本写入 jsonl
- 文件超过 max_bytes 时的单备份轮转
- 并发写入串行化（asyncio.gather）
- 不可序列化字段不抛异常
- build_decision_record 的 decision_zone 推导
"""

from __future__ import annotations

import asyncio
import json

import pytest

from astrbot.core.router_decision_logger import (
    RouterDecisionLogger,
    build_decision_record,
)

# ── basic logging ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_basic_log_writes_jsonl_line(tmp_path):
    logger = RouterDecisionLogger(tmp_path / "decisions.jsonl")

    await logger.log({"a": 1, "msg": "你好"})
    await logger.log({"a": 2, "msg": "再来一条"})

    lines = (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1, "msg": "你好"}
    assert json.loads(lines[1]) == {"a": 2, "msg": "再来一条"}


@pytest.mark.asyncio
async def test_directory_auto_created(tmp_path):
    """父目录不存在时应自动创建。"""
    path = tmp_path / "nested" / "dir" / "decisions.jsonl"
    logger = RouterDecisionLogger(path)
    await logger.log({"x": 1})
    assert path.exists()


@pytest.mark.asyncio
async def test_non_serializable_record_skipped_silently(tmp_path):
    logger = RouterDecisionLogger(tmp_path / "decisions.jsonl")
    # set() is not JSON-serializable
    await logger.log({"bad": {1, 2, 3}})
    # 不应抛错，且文件保持不存在或为空
    target = tmp_path / "decisions.jsonl"
    assert not target.exists() or target.read_text() == ""


# ── rotation ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rotation_when_exceeds_max_bytes(tmp_path):
    """文件超出 max_bytes 时，应轮转到 .1 备份并开新文件。"""
    path = tmp_path / "decisions.jsonl"
    logger = RouterDecisionLogger(path, max_bytes=200)

    # 每条 ~80 字节，写 5 条肯定触发轮转
    for i in range(5):
        await logger.log({"i": i, "pad": "x" * 50})

    backup = path.with_name("decisions.jsonl.1")
    assert backup.exists(), "轮转后应当生成 .1 备份"
    assert path.exists(), "轮转后主文件应继续写入"

    # 主文件不超过 max_bytes（允许略超：单条记录大于 max_bytes 的极端情况）
    assert path.stat().st_size <= 200 + 100


@pytest.mark.asyncio
async def test_second_rotation_overwrites_old_backup(tmp_path):
    """第二次轮转应丢掉旧的 .1，避免无限增长。"""
    path = tmp_path / "decisions.jsonl"
    logger = RouterDecisionLogger(path, max_bytes=100)

    for i in range(30):
        await logger.log({"i": i, "pad": "y" * 30})

    backup = path.with_name("decisions.jsonl.1")
    assert backup.exists()
    # 旧 .1 被覆盖：备份文件大小不应超过两倍 max_bytes
    assert backup.stat().st_size <= 200


# ── concurrency ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_logs_all_persisted(tmp_path):
    """asyncio.gather 并发调用 log，所有记录都应完整写入、无 race。"""
    logger = RouterDecisionLogger(tmp_path / "decisions.jsonl")

    n = 50
    await asyncio.gather(*(logger.log({"i": i}) for i in range(n)))

    lines = (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == n
    indices = sorted(json.loads(line)["i"] for line in lines)
    assert indices == list(range(n))


# ── build_decision_record ────────────────────────────────────────────────────


def test_build_record_decision_zone_auto_for_high_rule_confidence():
    rec = build_decision_record(
        message="生成图片",
        umo="qq:GroupMessage:1_2",
        platform_id="qqbot",
        category="skill",
        intent_type="dreamina_image",
        confidence=0.97,
        workflow_kind=None,
        skill_name="dreamina_plugin",
        matched_by="rule",
        llm_called=False,
        fallback_threshold=0.75,
        latency_ms=1.234,
    )
    assert rec["decision_zone"] == "auto"
    assert rec["confidence"] == 0.97
    assert rec["latency_ms"] == 1.234
    assert rec["msg_preview"] == "生成图片"
    assert "ts" in rec
    assert "span_id" not in rec


def test_build_record_decision_zone_fallback_when_low_confidence():
    rec = build_decision_record(
        message="一些模糊的话",
        umo="qq:GroupMessage:1_2",
        platform_id="qqbot",
        category="conversation",
        intent_type="general",
        confidence=0.4,
        workflow_kind=None,
        skill_name=None,
        matched_by="default",
        llm_called=False,
        fallback_threshold=0.75,
        latency_ms=0.5,
    )
    assert rec["decision_zone"] == "fallback"


def test_build_record_decision_zone_auto_for_llm_above_threshold():
    rec = build_decision_record(
        message="帮我写个营销方案",
        umo="qq:GroupMessage:1_2",
        platform_id="qqbot",
        category="task",
        intent_type="marketing_plan",
        confidence=0.82,
        workflow_kind="marketing_plan",
        skill_name=None,
        matched_by="llm",
        llm_called=True,
        fallback_threshold=0.75,
        latency_ms=420.0,
    )
    assert rec["decision_zone"] == "auto"
    assert rec["llm_called"] is True


def test_build_record_msg_preview_truncated():
    long_msg = "A" * 500
    rec = build_decision_record(
        message=long_msg,
        umo="qq",
        platform_id="qqbot",
        category="conversation",
        intent_type="general",
        confidence=0.4,
        workflow_kind=None,
        skill_name=None,
        matched_by="default",
        llm_called=False,
        fallback_threshold=0.75,
        latency_ms=0.5,
    )
    assert len(rec["msg_preview"]) == 200


def test_build_record_with_span_id_and_extra():
    rec = build_decision_record(
        message="x",
        umo="qq",
        platform_id="qqbot",
        category="task",
        intent_type="t",
        confidence=0.9,
        workflow_kind="marketing_plan",
        skill_name=None,
        matched_by="rule",
        llm_called=False,
        fallback_threshold=0.75,
        latency_ms=1,
        span_id="abc-123",
        extra={"reason": "test"},
    )
    assert rec["span_id"] == "abc-123"
    assert rec["extra"] == {"reason": "test"}
