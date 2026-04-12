import pytest

from astrbot.core.harness import (
    HarnessEngine,
    HarnessMemoryPromoter,
    HarnessMemoryStore,
    HarnessTaskCreateRequest,
    HarnessTaskStore,
)


@pytest.mark.asyncio
async def test_complete_task_promotes_memory_and_records_event(tmp_path):
    task_store = HarnessTaskStore(tmp_path / "harness.db")
    memory_store = HarnessMemoryStore(tmp_path / "harness_memory.db")
    promoter = HarnessMemoryPromoter(memory_store)
    engine = HarnessEngine(task_store, memory_promoter=promoter)

    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="沉淀经验测试",
            conversation_id="conv-mem",
            platform_id="qq",
            session_id="qq:friend:mem",
            payload={},
        )
    )

    await engine.complete_task(task.task_id, result={"summary": "这次客户更关注转化率"})

    memories = await memory_store.list_for_session("qq:friend:mem")
    events = await task_store.list_events(task.task_id)

    assert len(memories) == 1
    assert memories[0].summary == "这次客户更关注转化率"
    assert any(event.event_type == "memory_promoted" for event in events)
