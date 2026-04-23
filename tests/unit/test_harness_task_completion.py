"""
测试 InternalAgentSubStage._maybe_complete_harness_task 的闭环逻辑。

验证：
1. LLM 完成响应后，活跃 Harness 任务被正确 complete
2. summary 写入 result，触发记忆提升
3. 已完成/已取消任务不会被重复操作
4. final_resp 为空时跳过
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

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
    engine = HarnessEngine(task_store, memory_promoter=HarnessMemoryPromoter(memory_store))

    umo = "qq:friend:123"
    task = await _setup_task(engine, umo)

    stage, plugin_ctx = _make_stage(engine)
    plugin_ctx.get_current_harness_task = AsyncMock(return_value=task)

    resp = LLMResponse(role="assistant", completion_text="这次营销计划重点放在短视频渠道。")
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
    engine = HarnessEngine(task_store, memory_promoter=HarnessMemoryPromoter(memory_store))

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
