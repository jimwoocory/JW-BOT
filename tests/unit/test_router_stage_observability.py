"""单测：RouterStage._record_classify_observability 的 trace + jsonl 双写。

只覆盖观测层（Phase R0.1 / R0.2）的接线点，不进入完整 pipeline。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from astrbot.core.pipeline.process_stage.router_stage import RouterStage
from astrbot.core.router import Intent
from astrbot.core.router_decision_logger import RouterDecisionLogger


def _make_stage(decision_logger, fallback_threshold=0.75):
    """Build a RouterStage without invoking __init__ side-effects."""
    stage = RouterStage.__new__(RouterStage)
    stage.ctx = MagicMock()
    stage.router = MagicMock()
    stage.router.fallback_threshold = fallback_threshold
    stage.decision_logger = decision_logger
    return stage


def _make_event(message="生成图片", umo="qq:GroupMessage:1_2", platform_id="qqbot"):
    event = MagicMock()
    event.message_str = message
    event.unified_msg_origin = umo
    event.get_platform_id.return_value = platform_id
    # event.trace 是一个 MagicMock，自动支持 .record(...) + .span_id
    event.trace = MagicMock()
    event.trace.span_id = "span-xyz"
    return event


def _make_intent(
    *,
    category="skill",
    intent_type="dreamina_image",
    confidence=0.97,
    workflow_kind=None,
    skill_name="dreamina_plugin",
    matched_by="rule",
):
    return Intent(
        category=category,
        intent_type=intent_type,
        confidence=confidence,
        workflow_kind=workflow_kind,
        skill_name=skill_name,
        metadata={"matched_by": matched_by},
    )


@pytest.mark.asyncio
async def test_records_trace_and_jsonl_for_rule_match(tmp_path):
    """规则命中场景：trace.record 调一次、jsonl 落一行。"""
    logger = RouterDecisionLogger(tmp_path / "decisions.jsonl")
    stage = _make_stage(logger)
    event = _make_event(message="生成图片", umo="qq:Group:1")
    intent = _make_intent()

    await stage._record_classify_observability(event, intent, latency_ms=1.5)

    # trace.record 应被调一次，第一个位置参数是 "router_classify"
    event.trace.record.assert_called_once()
    args, kwargs = event.trace.record.call_args
    assert args[0] == "router_classify"
    assert kwargs["category"] == "skill"
    assert kwargs["intent_type"] == "dreamina_image"
    assert kwargs["confidence"] == 0.97
    assert kwargs["matched_by"] == "rule"
    assert kwargs["llm_called"] is False
    assert kwargs["fallback_threshold"] == 0.75

    # jsonl 应有一条记录
    lines = (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["category"] == "skill"
    assert rec["matched_by"] == "rule"
    assert rec["llm_called"] is False
    assert rec["decision_zone"] == "auto"
    assert rec["span_id"] == "span-xyz"
    assert rec["msg_preview"] == "生成图片"
    assert rec["umo"] == "qq:Group:1"
    assert rec["platform_id"] == "qqbot"


@pytest.mark.asyncio
async def test_records_llm_called_when_matched_by_llm(tmp_path):
    logger = RouterDecisionLogger(tmp_path / "decisions.jsonl")
    stage = _make_stage(logger)
    event = _make_event()
    intent = _make_intent(
        category="task",
        intent_type="marketing_plan",
        confidence=0.82,
        workflow_kind="marketing_plan",
        skill_name=None,
        matched_by="llm",
    )

    await stage._record_classify_observability(event, intent, latency_ms=300.0)

    rec = json.loads(
        (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert rec["llm_called"] is True
    assert rec["matched_by"] == "llm"
    assert rec["decision_zone"] == "auto"  # confidence 0.82 >= 0.75
    assert rec["workflow_kind"] == "marketing_plan"


@pytest.mark.asyncio
async def test_records_fallback_zone_for_low_confidence_default(tmp_path):
    logger = RouterDecisionLogger(tmp_path / "decisions.jsonl")
    stage = _make_stage(logger)
    event = _make_event(message="一些闲聊")
    intent = Intent(
        category="conversation",
        intent_type="general",
        confidence=0.4,
        metadata={},  # 没有 matched_by → 应被记为 default
    )

    await stage._record_classify_observability(event, intent, latency_ms=0.3)

    rec = json.loads(
        (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert rec["matched_by"] == "default"
    assert rec["decision_zone"] == "fallback"
    assert rec["llm_called"] is False


@pytest.mark.asyncio
async def test_no_decision_logger_does_not_crash(tmp_path):
    """decision_logger=None 时仅写 trace、不应抛错。"""
    stage = _make_stage(decision_logger=None)
    event = _make_event()
    intent = _make_intent()

    # 不应抛出任何异常
    await stage._record_classify_observability(event, intent, latency_ms=1.0)

    event.trace.record.assert_called_once()


@pytest.mark.asyncio
async def test_trace_record_failure_does_not_block_jsonl(tmp_path):
    """trace.record 抛错时仍应继续写 jsonl，确保观测层一处坏不影响另一处。"""
    logger = RouterDecisionLogger(tmp_path / "decisions.jsonl")
    stage = _make_stage(logger)
    event = _make_event()
    event.trace.record.side_effect = RuntimeError("trace broken")
    intent = _make_intent()

    await stage._record_classify_observability(event, intent, latency_ms=1.0)

    # jsonl 文件仍然应有一行
    lines = (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
