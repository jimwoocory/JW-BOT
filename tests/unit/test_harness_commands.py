from unittest.mock import AsyncMock, MagicMock

import pytest

from astrbot.builtin_stars.builtin_commands.commands.harness import HarnessCommands
from astrbot.core.harness import (
    HarnessEngine,
    HarnessTaskCreateRequest,
    HarnessTaskStore,
    create_workflow_request,
)


@pytest.mark.asyncio
async def test_task_new_creates_task_and_sets_result(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    async def _snapshot_getter(conversation_id: str):
        return {
            "conversation_id": conversation_id,
            "total_items": 5,
            "raw_message_items": 5,
            "summary_leaf_items": 0,
            "last_ingested_seq": 5,
        }

    engine = HarnessEngine(store, session_snapshot_getter=_snapshot_getter)

    context = MagicMock()
    context.harness_engine = engine
    context.harness_store = store
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-1"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:1"
    event.message_str = "/task new 制定推广方案"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_new(event, "制定推广方案")

    tasks = await store.list_tasks_for_conversation("conv-1")
    assert len(tasks) == 1
    assert tasks[0].title == "制定推广方案"
    assert tasks[0].payload["session_context"]["total_items"] == 5
    event.set_result.assert_called_once()


@pytest.mark.asyncio
async def test_task_ls_shows_current_conversation_tasks(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    await store.create_task(
        HarnessTaskCreateRequest(
            title="任务 A",
            conversation_id="conv-2",
            platform_id="qq",
            session_id="qq:friend:2",
        ),
        task_id="task-a",
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = None
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-2"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:2"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_ls(event)

    event.set_result.assert_called_once()


@pytest.mark.asyncio
async def test_task_show_requires_existing_task(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    context = MagicMock()
    context.harness_store = store
    context.harness_engine = None
    context.conversation_manager = MagicMock()

    event = MagicMock()
    cmd = HarnessCommands(context)

    await cmd.task_show(event, "missing-task")

    event.set_result.assert_called_once()


@pytest.mark.asyncio
async def test_task_start_updates_status_for_current_conversation(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    created = await engine.create_task(
        HarnessTaskCreateRequest(
            title="任务启动测试",
            conversation_id="conv-3",
            platform_id="qq",
            session_id="qq:friend:3",
        )
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = engine
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-3"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:3"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_start(event, created.task_id, "开始执行")

    updated = await store.get_task(created.task_id)
    assert updated is not None
    assert updated.status == "in_progress"


@pytest.mark.asyncio
async def test_task_done_updates_result(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    created = await engine.create_task(
        HarnessTaskCreateRequest(
            title="任务完成测试",
            conversation_id="conv-4",
            platform_id="qq",
            session_id="qq:friend:4",
        )
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = engine
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-4"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:4"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_done(event, created.task_id, "已完成首版方案")

    updated = await store.get_task(created.task_id)
    assert updated is not None
    assert updated.status == "completed"
    assert updated.result["summary"] == "已完成首版方案"


@pytest.mark.asyncio
async def test_task_operation_rejects_other_conversation_task(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    created = await engine.create_task(
        HarnessTaskCreateRequest(
            title="跨会话保护",
            conversation_id="conv-a",
            platform_id="qq",
            session_id="qq:friend:a",
        )
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = engine
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-b"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:b"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_review(event, created.task_id, "不应成功")

    unchanged = await store.get_task(created.task_id)
    assert unchanged is not None
    assert unchanged.status == "pending"


@pytest.mark.asyncio
async def test_task_approve_creates_review_record(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    created = await engine.create_task(
        HarnessTaskCreateRequest(
            title="审批测试",
            conversation_id="conv-review",
            platform_id="qq",
            session_id="qq:friend:review",
        )
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = engine
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-review"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:review"
    event.get_platform_id.return_value = "qq"
    event.get_sender_id.return_value = "boss-1"

    cmd = HarnessCommands(context)
    await cmd.task_approve(event, created.task_id, "同意推进")

    reviews = await store.list_reviews(created.task_id)
    assert len(reviews) == 1
    assert reviews[0].decision == "approved"
    assert reviews[0].reviewer_id == "boss-1"


@pytest.mark.asyncio
async def test_task_reject_blocks_task_and_records_review(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    created = await engine.create_task(
        HarnessTaskCreateRequest(
            title="驳回测试",
            conversation_id="conv-reject",
            platform_id="qq",
            session_id="qq:friend:reject",
        )
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = engine
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-reject"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:reject"
    event.get_platform_id.return_value = "qq"
    event.get_sender_id.return_value = "boss-2"

    cmd = HarnessCommands(context)
    await cmd.task_reject(event, created.task_id, "预算不足，先暂停")

    updated = await store.get_task(created.task_id)
    reviews = await store.list_reviews(created.task_id)
    assert updated is not None
    assert updated.status == "blocked"
    assert len(reviews) == 1
    assert reviews[0].decision == "rejected"


@pytest.mark.asyncio
async def test_task_intake_creates_workflow_task(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)

    context = MagicMock()
    context.harness_engine = engine
    context.harness_store = store
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-workflow"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:workflow"
    event.message_str = "/task intake marketing_plan 制定本周推广计划"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_intake(event, "marketing_plan", "制定本周推广计划")

    tasks = await store.list_tasks_for_conversation("conv-workflow")
    assert len(tasks) == 1
    assert tasks[0].domain == "marketing"
    assert tasks[0].payload["workflow_kind"] == "marketing_plan"
    assert tasks[0].payload["review_required_by_default"] is True


@pytest.mark.asyncio
async def test_task_intake_rejects_invalid_workflow_kind(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)

    context = MagicMock()
    context.harness_engine = engine
    context.harness_store = store
    context.conversation_manager = MagicMock()

    event = MagicMock()

    cmd = HarnessCommands(context)
    await cmd.task_intake(event, "unknown_kind", "测试")

    event.set_result.assert_called_once()


@pytest.mark.asyncio
async def test_task_done_routes_workflow_task_to_review_when_required(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    created = await engine.create_task(
        create_workflow_request(
            workflow_kind="marketing_plan",
            brief="制定本周推广计划",
            conversation_id="conv-review-flow",
            platform_id="qq",
            session_id="qq:friend:review-flow",
            source="workflow_intake",
            message_text="/task intake marketing_plan 制定本周推广计划",
        )
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = engine
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-review-flow"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:review-flow"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_done(
        event,
        created.task_id,
        '{"strategy":"A","channels":["小红书"],"timeline":"本周","kpis":["曝光"]}',
    )

    updated = await store.get_task(created.task_id)
    events = await store.list_events(created.task_id)
    assert updated is not None
    assert updated.status == "review_required"
    assert updated.result["workflow_validation"]["is_valid"] is True
    assert any(event_.event_type == "workflow_result_validated" for event_ in events)


@pytest.mark.asyncio
async def test_task_done_marks_project_followup_complete_when_result_valid(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    created = await engine.create_task(
        create_workflow_request(
            workflow_kind="project_followup",
            brief="整理项目进度",
            conversation_id="conv-project-flow",
            platform_id="qq",
            session_id="qq:friend:project-flow",
            source="workflow_intake",
            message_text="/task intake project_followup 整理项目进度",
        )
    )

    context = MagicMock()
    context.harness_store = store
    context.harness_engine = engine
    context.conversation_manager = MagicMock()
    context.conversation_manager.get_curr_conversation_id = AsyncMock(
        return_value="conv-project-flow"
    )

    event = MagicMock()
    event.unified_msg_origin = "qq:friend:project-flow"
    event.get_platform_id.return_value = "qq"

    cmd = HarnessCommands(context)
    await cmd.task_done(
        event,
        created.task_id,
        '{"progress":"已完成初稿","risks":["待确认预算"],"next_actions":["老板确认"]}',
    )

    updated = await store.get_task(created.task_id)
    assert updated is not None
    assert updated.status == "completed"
    assert updated.result["workflow_validation"]["is_valid"] is True
