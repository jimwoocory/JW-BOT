"""
测试 InternalAgentSubStage._maybe_complete_harness_task 的闭环逻辑。

验证：
1. LLM 完成响应后，活跃 Harness 任务被正确 complete
2. summary 写入 result，触发记忆提升
3. 已完成/已取消任务不会被重复操作
4. final_resp 为空时跳过
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.harness import (
    HarnessEngine,
    HarnessMemoryPromoter,
    HarnessMemoryStore,
    HarnessTaskCreateRequest,
    HarnessTaskStore,
)
from astrbot.core.provider.entities import LLMResponse

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_stage(engine):
    """Build a minimal InternalAgentSubStage with mocked context."""
    from astrbot.core.pipeline.process_stage.method.agent_sub_stages.internal import (
        InternalAgentSubStage,
    )

    stage = InternalAgentSubStage.__new__(InternalAgentSubStage)

    plugin_ctx = MagicMock()
    plugin_ctx.harness_engine = engine

    stage.ctx = MagicMock()
    stage.ctx.plugin_manager.context = plugin_ctx

    return stage, plugin_ctx


def _make_event(umo: str):
    event = MagicMock()
    event.unified_msg_origin = umo
    return event


async def _setup_task(engine, umo: str, *, workflow_kind="marketing_plan"):
    """Create a pending task and wire get_current_harness_task to return it."""
    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="测试任务",
            conversation_id="conv-close-loop",
            platform_id="qq",
            session_id=umo,
            payload={"workflow_kind": workflow_kind},
        )
    )
    return task


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_complete_task_on_llm_finish(tmp_path):
    """正常路径：LLM 响应后任务变为 completed，summary 写入，记忆提升。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    memory_store = HarnessMemoryStore(tmp_path / "memory.db")
    engine = HarnessEngine(
        task_store, memory_promoter=HarnessMemoryPromoter(memory_store)
    )

    umo = "qq:friend:123"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    resp = LLMResponse(
        role="assistant", completion_text="这次营销计划重点放在短视频渠道。"
    )
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    completed = await task_store.get_task(task.task_id)
    assert completed.status == "completed"
    assert "这次营销计划" in completed.result.get("summary", "")

    memories = await memory_store.list_for_session(umo)
    assert len(memories) == 1
    assert "这次营销计划" in memories[0].summary


@pytest.mark.asyncio
async def test_skip_when_final_resp_none(tmp_path):
    """final_resp 为 None 时不操作任务。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(task_store)

    umo = "qq:friend:456"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    await stage._maybe_complete_harness_task(_make_event(umo), None)

    unchanged = await task_store.get_task(task.task_id)
    assert unchanged.status == "pending"


@pytest.mark.asyncio
async def test_skip_when_completion_text_empty(tmp_path):
    """completion_text 为空字符串时跳过。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(task_store)

    umo = "qq:friend:789"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    resp = LLMResponse(role="assistant", completion_text="   ")
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    unchanged = await task_store.get_task(task.task_id)
    assert unchanged.status == "pending"


@pytest.mark.asyncio
async def test_skip_already_completed_task(tmp_path):
    """已完成的任务不会被二次 complete（不抛出异常）。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(task_store)

    umo = "qq:friend:already"
    task = await _setup_task(engine, umo)
    await engine.complete_task(task.task_id, result={"summary": "已完成"})

    completed_task = await task_store.get_task(task.task_id)
    assert completed_task.status == "completed"

    stage, plugin_ctx = _make_stage(engine)
    # get_current_harness_task should return None for terminal tasks
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=None)

    resp = LLMResponse(role="assistant", completion_text="第二次响应")
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    # task still completed, not modified
    still_completed = await task_store.get_task(task.task_id)
    assert still_completed.status == "completed"
    assert still_completed.result.get("summary") == "已完成"


@pytest.mark.asyncio
async def test_skip_when_no_active_task(tmp_path):
    """没有活跃任务时静默跳过。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(task_store)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=None)

    resp = LLMResponse(role="assistant", completion_text="普通聊天回复")
    await stage._maybe_complete_harness_task(_make_event("qq:friend:noop"), resp)
    # no exception, nothing to assert beyond no crash


@pytest.mark.asyncio
async def test_skip_when_harness_engine_none(tmp_path):
    """harness_engine 为 None 时（系统未启用 Harness）静默跳过。"""
    stage, plugin_ctx = _make_stage(engine=None)
    plugin_ctx.harness_engine = None

    resp = LLMResponse(role="assistant", completion_text="some response")
    await stage._maybe_complete_harness_task(_make_event("qq:friend:noharness"), resp)


@pytest.mark.asyncio
async def test_summary_truncated_to_200_chars(tmp_path):
    """超长 completion_text 的 summary 被截断到 200 字符。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    memory_store = HarnessMemoryStore(tmp_path / "memory.db")
    engine = HarnessEngine(
        task_store, memory_promoter=HarnessMemoryPromoter(memory_store)
    )

    umo = "qq:friend:long"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    long_text = "A" * 500
    resp = LLMResponse(role="assistant", completion_text=long_text)
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    completed = await task_store.get_task(task.task_id)
    assert len(completed.result["summary"]) == 200
    assert len(completed.result["response_preview"]) == 500


# ── Phase 0.2 sensor hardening tests ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_quality_field_set_to_success(tmp_path):
    """正常响应时 result.quality == 'success'。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    memory_store = HarnessMemoryStore(tmp_path / "memory.db")
    engine = HarnessEngine(
        task_store, memory_promoter=HarnessMemoryPromoter(memory_store)
    )

    umo = "qq:friend:quality"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    resp = LLMResponse(role="assistant", completion_text="正常完成的方案要点。")
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    completed = await task_store.get_task(task.task_id)
    assert completed.status == "completed"
    assert completed.result.get("quality") == "success"


@pytest.mark.asyncio
async def test_error_role_routes_to_fail_task(tmp_path):
    """LLMResponse.role == 'err' 时任务走 fail_task，不晋升记忆。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    memory_store = HarnessMemoryStore(tmp_path / "memory.db")
    engine = HarnessEngine(
        task_store, memory_promoter=HarnessMemoryPromoter(memory_store)
    )

    umo = "qq:friend:errrole"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    resp = LLMResponse(role="err", completion_text="provider explosion")
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    failed = await task_store.get_task(task.task_id)
    assert failed.status == "failed"
    memories = await memory_store.list_for_session(umo)
    assert memories == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_text",
    [
        "All chat models failed: BadRequestError: Error code: 400 - bad json",
        "RateLimitError: 429 too many requests",
        "AuthenticationError: invalid api key",
        "APIConnectionError: timed out",
        "Error code: 503 - service unavailable",
    ],
)
async def test_known_error_patterns_route_to_fail_task(tmp_path, error_text):
    """已知的 LLM 错误关键词命中后走 fail_task。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    memory_store = HarnessMemoryStore(tmp_path / "memory.db")
    engine = HarnessEngine(
        task_store, memory_promoter=HarnessMemoryPromoter(memory_store)
    )

    umo = f"qq:friend:err-{hash(error_text) & 0xFFFF:x}"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    resp = LLMResponse(role="assistant", completion_text=error_text)
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    failed = await task_store.get_task(task.task_id)
    assert failed.status == "failed"
    memories = await memory_store.list_for_session(umo)
    assert memories == []


@pytest.mark.asyncio
async def test_markdown_decorations_stripped_from_summary(tmp_path):
    """summary 字段不应保留 # 标题 / ** 加粗 / > 引用 等装饰符号。"""
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    memory_store = HarnessMemoryStore(tmp_path / "memory.db")
    engine = HarnessEngine(
        task_store, memory_promoter=HarnessMemoryPromoter(memory_store)
    )

    umo = "qq:friend:md"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    md_text = (
        "## 推广计划要点\n\n"
        "**核心**：聚焦短视频与直播投放，配合 [试驾券](https://example.com) 促转化。\n\n"
        "> 注意：以上为通用方案。"
    )
    resp = LLMResponse(role="assistant", completion_text=md_text)
    await stage._maybe_complete_harness_task(_make_event(umo), resp)

    completed = await task_store.get_task(task.task_id)
    summary = completed.result["summary"]
    assert "##" not in summary
    assert "**" not in summary
    assert summary.lstrip()[0] != "#"
    # 至少保留一段实质内容
    assert "推广计划要点" in summary or "短视频" in summary or "试驾券" in summary


def test_classify_response_quality_pure():
    """直接测试分类器（无需 stage / engine）。"""
    from astrbot.core.pipeline.process_stage.method.agent_sub_stages.internal import (
        _classify_response_quality,
    )

    ok = LLMResponse(role="assistant", completion_text="一切正常")
    assert _classify_response_quality(ok, ok.completion_text) == "success"

    err_role = LLMResponse(role="err", completion_text="anything")
    assert _classify_response_quality(err_role, err_role.completion_text) == "error"

    err_text = LLMResponse(
        role="assistant", completion_text="All chat models failed: BadRequestError ..."
    )
    assert _classify_response_quality(err_text, err_text.completion_text) == "error"


def test_extract_summary_pure():
    """直接测试摘要清洗。"""
    from astrbot.core.pipeline.process_stage.method.agent_sub_stages.internal import (
        _extract_summary,
    )

    md = "## 标题\n\n这是**正文**第一段，包含 [链接](https://x)。\n\n第二段。"
    out = _extract_summary(md)
    assert "##" not in out
    assert "**" not in out
    assert "https" not in out
    # 链接锚文本保留
    assert "链接" in out

    # 长文本被截断到 max_len
    long = "A" * 500
    assert len(_extract_summary(long, max_len=200)) == 200
