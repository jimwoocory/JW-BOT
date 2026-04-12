from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from astrbot.core.harness import (
    HarnessCognitionProvider,
    HarnessEngine,
    HarnessTaskCreateRequest,
    HarnessMemoryStore,
    HarnessTaskStore,
)


@pytest.mark.asyncio
async def test_cognition_provider_builds_persona_kb_and_recent_task_snapshot(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)

    completed = await engine.create_task(
        HarnessTaskCreateRequest(
            title="上周方案",
            conversation_id="conv-old",
            platform_id="qq",
            session_id="qq:friend:100",
            payload={},
        )
    )
    await engine.complete_task(completed.task_id, result={"summary": "已经做过一次投放方案"})

    persona_manager = MagicMock()
    persona_manager.get_persona_v3_by_id.return_value = {"name": "marketing-boss"}

    kb_helper = MagicMock()
    kb_helper.kb.kb_name = "公司知识库"
    kb_manager = MagicMock()
    kb_manager.get_kb = AsyncMock(return_value=kb_helper)
    memory_store = HarnessMemoryStore(tmp_path / "harness_memory.db")
    await memory_store.create_memory(
        session_id="qq:friend:100",
        conversation_id="conv-old",
        task_id="task-m1",
        domain="marketing",
        memory_kind="task_outcome",
        title="旧经验",
        summary="客户更在意成交线索",
        payload={"result": {"summary": "客户更在意成交线索"}},
    )

    provider = HarnessCognitionProvider(
        persona_manager=persona_manager,
        kb_manager=kb_manager,
        harness_store=store,
        memory_store=memory_store,
    )

    with (
        patch(
            "astrbot.core.harness.cognition.sp.get_async",
            AsyncMock(return_value={"persona_id": "marketing-boss"}),
        ),
        patch(
            "astrbot.core.harness.cognition.sp.session_get",
            AsyncMock(return_value={"kb_ids": ["kb-1"]}),
        ),
    ):
        snapshot = await provider.build_snapshot(
            HarnessTaskCreateRequest(
                title="本周新方案",
                conversation_id="conv-new",
                platform_id="qq",
                session_id="qq:friend:100",
                payload={},
            )
        )

    assert snapshot.persona_id == "marketing-boss"
    assert snapshot.persona_name == "marketing-boss"
    assert snapshot.knowledge_base_names == ["公司知识库"]
    assert len(snapshot.recent_task_summaries) == 1
    assert snapshot.recent_task_summaries[0]["title"] == "上周方案"
    assert len(snapshot.recent_memories) == 1
    assert snapshot.recent_memories[0]["summary"] == "客户更在意成交线索"


@pytest.mark.asyncio
async def test_engine_create_task_links_cognitive_context(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")

    async def _cognitive_snapshot(request: HarnessTaskCreateRequest):
        return {
            "persona_name": "ops",
            "knowledge_base_names": ["企业资料"],
            "recent_task_summaries": [{"task_id": "t1", "title": "历史任务"}],
        }

    engine = HarnessEngine(store, cognitive_snapshot_getter=_cognitive_snapshot)

    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="认知挂载测试",
            conversation_id="conv-cog",
            platform_id="qq",
            session_id="qq:friend:cog",
            payload={},
        )
    )

    assert task.payload["cognitive_context"]["persona_name"] == "ops"
    assert task.payload["cognitive_context"]["knowledge_base_names"] == ["企业资料"]

    events = await store.list_events(task.task_id)
    assert [event.event_type for event in events] == [
        "task_created",
        "cognitive_context_linked",
    ]
