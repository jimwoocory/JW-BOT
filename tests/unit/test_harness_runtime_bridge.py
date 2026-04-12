from asyncio import Queue
from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.core.harness import HarnessEngine, HarnessTaskCreateRequest, HarnessTaskStore
from astrbot.core.star.context import Context


def _build_context(store: HarnessTaskStore, engine: HarnessEngine) -> Context:
    conversation_manager = MagicMock()
    conversation_manager.get_curr_conversation_id = AsyncMock(return_value="conv-bridge")

    return Context(
        event_queue=Queue(),
        config=MagicMock(),
        db=MagicMock(),
        provider_manager=MagicMock(),
        platform_manager=MagicMock(),
        conversation_manager=conversation_manager,
        message_history_manager=MagicMock(),
        persona_manager=MagicMock(),
        astrbot_config_mgr=MagicMock(),
        knowledge_base_manager=MagicMock(),
        cron_manager=MagicMock(),
        subagent_orchestrator=None,
        harness_engine=engine,
        harness_store=store,
    )


@pytest.mark.asyncio
async def test_context_append_harness_trace_records_on_latest_active_task(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    context = _build_context(store, engine)

    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="执行轨迹测试",
            conversation_id="conv-bridge",
            platform_id="qq",
            session_id="qq:friend:bridge",
        )
    )
    await engine.mark_in_progress(task.task_id, note="running")

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:bridge"

    recorded = await context.append_harness_trace(
        event,
        "tool_call_started",
        {"tool_name": "opencli"},
    )

    assert recorded is True
    events = await store.list_events(task.task_id)
    assert events[-1].event_type == "tool_call_started"
    assert events[-1].payload["tool_name"] == "opencli"


@pytest.mark.asyncio
async def test_context_append_harness_trace_returns_false_without_active_task(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    context = _build_context(store, engine)

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:bridge"

    recorded = await context.append_harness_trace(
        event,
        "assistant_response_saved",
        {"response_preview": "ok"},
    )

    assert recorded is False
