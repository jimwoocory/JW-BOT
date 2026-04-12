import pytest

from astrbot.core.harness import HarnessEngine, HarnessTaskCreateRequest, HarnessTaskStore


@pytest.mark.asyncio
async def test_create_task_persists_task_and_created_event(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)

    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="制定小红书推广策略",
            conversation_id="conv-1",
            platform_id="qq",
            session_id="qq:friend:1",
            domain="marketing",
            payload={"company": "JW"},
        )
    )

    assert task.status == "pending"
    assert task.domain == "marketing"

    events = await store.list_events(task.task_id)
    assert len(events) == 1
    assert events[0].event_type == "task_created"


@pytest.mark.asyncio
async def test_create_task_links_session_context_snapshot(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")

    async def _snapshot_getter(conversation_id: str):
        return {
            "conversation_id": conversation_id,
            "total_items": 8,
            "raw_message_items": 6,
            "summary_leaf_items": 1,
            "last_ingested_seq": 6,
        }

    engine = HarnessEngine(store, session_snapshot_getter=_snapshot_getter)

    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="绑定会话上下文",
            conversation_id="conv-lossless",
            platform_id="qq",
            session_id="qq:friend:lossless",
        )
    )

    assert task.payload["session_context"]["conversation_id"] == "conv-lossless"
    assert task.payload["session_context"]["summary_leaf_items"] == 1

    events = await store.list_events(task.task_id)
    assert [event.event_type for event in events] == [
        "task_created",
        "session_context_linked",
    ]
    assert events[-1].payload["total_items"] == 8


@pytest.mark.asyncio
async def test_update_status_appends_status_event(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="客户项目跟进",
            conversation_id="conv-2",
            platform_id="qq",
            session_id="qq:friend:2",
        )
    )

    updated = await engine.mark_review_required(task.task_id, reviewer_note="待老板确认")

    assert updated.status == "review_required"
    events = await store.list_events(task.task_id)
    assert [event.event_type for event in events] == [
        "task_created",
        "status_changed",
    ]
    assert events[-1].payload["status"] == "review_required"
    assert events[-1].payload["reviewer_note"] == "待老板确认"


@pytest.mark.asyncio
async def test_append_trace_rejects_terminal_task(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)
    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="完成交付",
            conversation_id="conv-3",
            platform_id="qq",
            session_id="qq:friend:3",
        )
    )
    await engine.complete_task(task.task_id, result={"output": "ok"})

    with pytest.raises(RuntimeError):
        await engine.append_trace(
            task.task_id,
            "tool_result",
            {"tool": "opencli"},
        )


@pytest.mark.asyncio
async def test_list_tasks_for_conversation_returns_latest_first(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")

    first = await store.create_task(
        HarnessTaskCreateRequest(
            title="任务 1",
            conversation_id="conv-4",
            platform_id="qq",
            session_id="qq:friend:4",
        ),
        task_id="task-1",
    )
    second = await store.create_task(
        HarnessTaskCreateRequest(
            title="任务 2",
            conversation_id="conv-4",
            platform_id="qq",
            session_id="qq:friend:4",
        ),
        task_id="task-2",
    )

    assert first.task_id == "task-1"
    assert second.task_id == "task-2"

    tasks = await store.list_tasks_for_conversation("conv-4")
    assert [task.task_id for task in tasks] == ["task-2", "task-1"]


@pytest.mark.asyncio
async def test_create_and_list_reviews(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    task = await store.create_task(
        HarnessTaskCreateRequest(
            title="任务审查测试",
            conversation_id="conv-review",
            platform_id="qq",
            session_id="qq:friend:review",
        ),
        task_id="task-review",
    )

    review = await store.create_review(
        task.task_id,
        "reviewer-1",
        "approved",
        "可以执行",
    )

    reviews = await store.list_reviews(task.task_id)
    assert len(reviews) == 1
    assert reviews[0].review_id == review.review_id
    assert reviews[0].decision == "approved"


@pytest.mark.asyncio
async def test_get_latest_task_for_conversation_skips_terminal_by_default(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)

    first = await engine.create_task(
        HarnessTaskCreateRequest(
            title="已完成任务",
            conversation_id="conv-latest",
            platform_id="qq",
            session_id="qq:friend:latest",
        )
    )
    await engine.complete_task(first.task_id, result={"summary": "done"})

    second = await engine.create_task(
        HarnessTaskCreateRequest(
            title="进行中任务",
            conversation_id="conv-latest",
            platform_id="qq",
            session_id="qq:friend:latest",
        )
    )
    await engine.mark_in_progress(second.task_id, note="working")

    latest = await store.get_latest_task_for_conversation("conv-latest")
    assert latest is not None
    assert latest.task_id == second.task_id
    assert latest.status == "in_progress"


@pytest.mark.asyncio
async def test_list_tasks_for_session_filters_by_status(tmp_path):
    store = HarnessTaskStore(tmp_path / "harness.db")
    engine = HarnessEngine(store)

    completed = await engine.create_task(
        HarnessTaskCreateRequest(
            title="已完成",
            conversation_id="conv-s1",
            platform_id="qq",
            session_id="qq:friend:session-1",
        )
    )
    blocked = await engine.create_task(
        HarnessTaskCreateRequest(
            title="已阻塞",
            conversation_id="conv-s2",
            platform_id="qq",
            session_id="qq:friend:session-1",
        )
    )
    pending = await engine.create_task(
        HarnessTaskCreateRequest(
            title="待处理",
            conversation_id="conv-s3",
            platform_id="qq",
            session_id="qq:friend:session-1",
        )
    )

    await engine.complete_task(completed.task_id, result={"summary": "done"})
    await engine.set_status(blocked.task_id, "blocked", event_payload={"reason": "wait"})

    tasks = await store.list_tasks_for_session(
        "qq:friend:session-1",
        statuses=("completed", "blocked"),
    )
    task_ids = {task.task_id for task in tasks}
    assert completed.task_id in task_ids
    assert blocked.task_id in task_ids
    assert pending.task_id not in task_ids
