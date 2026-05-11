"""Unit tests for ``astrbot.core.case.engine.CaseEngine``."""

from __future__ import annotations

import pytest
import pytest_asyncio

from astrbot.core.case import CaseEngine, CaseStore
from astrbot.core.harness import HarnessTaskCreateRequest, HarnessTaskStore


@pytest_asyncio.fixture
async def engine(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    harness_store = HarnessTaskStore(tmp_path / "harness.db")
    return CaseEngine(store, harness_store=harness_store)


# ---------------------------------------------------------------------------
# create_case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_case_strips_whitespace(engine):
    case = await engine.create_case(
        name="  春节推广  ",
        platform_id="qq",
        session_id="sess",
        client_name="  客户A  ",
    )
    assert case.name == "春节推广"
    assert case.client_name == "客户A"


@pytest.mark.asyncio
async def test_create_case_rejects_empty_name(engine):
    with pytest.raises(ValueError):
        await engine.create_case(name="   ", platform_id="qq", session_id="sess")


@pytest.mark.asyncio
async def test_create_case_treats_blank_client_as_none(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess", client_name="   "
    )
    assert case.client_name is None


# ---------------------------------------------------------------------------
# attach_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attach_task_appends_to_task_ids(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    updated = await engine.attach_task(case.case_id, "task-1")
    assert updated.task_ids == ["task-1"]


@pytest.mark.asyncio
async def test_attach_task_is_idempotent(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    await engine.attach_task(case.case_id, "task-1")
    again = await engine.attach_task(case.case_id, "task-1")
    assert again.task_ids == ["task-1"]


@pytest.mark.asyncio
async def test_attach_task_raises_for_unknown_case(engine):
    with pytest.raises(LookupError):
        await engine.attach_task("unknown", "task-1")


# ---------------------------------------------------------------------------
# add_deliverable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_deliverable_records_kind_path_and_version(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    updated = await engine.add_deliverable(
        case.case_id, kind="text", path="data/draft.md", version=1
    )
    assert len(updated.deliverables) == 1
    deliverable = updated.deliverables[0]
    assert deliverable["kind"] == "text"
    assert deliverable["path"] == "data/draft.md"
    assert deliverable["version"] == 1
    assert "created_at" in deliverable


@pytest.mark.asyncio
async def test_add_deliverable_extra_metadata_round_trips(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    updated = await engine.add_deliverable(
        case.case_id,
        kind="image",
        path="data/draft.png",
        extra={"source": "midjourney", "prompt": "春节红色"},
    )
    deliverable = updated.deliverables[0]
    assert deliverable["source"] == "midjourney"
    assert deliverable["prompt"] == "春节红色"


# ---------------------------------------------------------------------------
# assign_role / bump_version / set_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_role_replaces_previous_user(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    first = await engine.assign_role(case.case_id, "业务", "u1")
    second = await engine.assign_role(case.case_id, "业务", "u2")
    assert first.roles == {"业务": "u1"}
    assert second.roles == {"业务": "u2"}


@pytest.mark.asyncio
async def test_bump_version_increments_and_logs(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    after = await engine.bump_version(case.case_id)
    assert after.version == 2
    events = await engine.store.list_events(case.case_id)
    assert any(e.event_type == "version_bumped" for e in events)


@pytest.mark.asyncio
async def test_set_status_no_op_when_unchanged(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    await engine.set_status(case.case_id, "initiated")
    events = await engine.store.list_events(case.case_id)
    assert not any(e.event_type == "status_changed" for e in events)


@pytest.mark.asyncio
async def test_set_status_records_transition(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    updated = await engine.set_status(case.case_id, "drafting")
    assert updated.status == "drafting"
    events = await engine.store.list_events(case.case_id)
    transition = [e for e in events if e.event_type == "status_changed"][0]
    assert transition.payload == {"from": "initiated", "to": "drafting"}


# ---------------------------------------------------------------------------
# archive_case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_case_sets_status_and_invokes_hook(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    fired: list[str] = []

    async def hook(case):
        fired.append(case.case_id)

    engine = CaseEngine(store, archive_hook=hook)
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    archived = await engine.archive_case(case.case_id)
    assert archived.status == "archived"
    assert fired == [case.case_id]


@pytest.mark.asyncio
async def test_archive_case_short_circuits_when_already_archived(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    fired: list[str] = []

    async def hook(case):
        fired.append(case.case_id)

    engine = CaseEngine(store, archive_hook=hook)
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    await engine.archive_case(case.case_id)
    again = await engine.archive_case(case.case_id)
    assert again.status == "archived"
    # Hook fires only the first time.
    assert fired == [case.case_id]


# ---------------------------------------------------------------------------
# get_current_case_for_session / get_case_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_case_returns_active_case(engine):
    case = await engine.create_case(
        name="active", platform_id="qq", session_id="sess"
    )
    found = await engine.get_current_case_for_session("sess")
    assert found is not None
    assert found.case_id == case.case_id


@pytest.mark.asyncio
async def test_get_current_case_excludes_archived(engine):
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    await engine.archive_case(case.case_id)
    assert await engine.get_current_case_for_session("sess") is None


@pytest.mark.asyncio
async def test_get_case_context_resolves_task_summaries(tmp_path):
    case_store = CaseStore(tmp_path / "cases.db")
    harness_store = HarnessTaskStore(tmp_path / "harness.db")
    engine = CaseEngine(case_store, harness_store=harness_store)

    task = await harness_store.create_task(
        HarnessTaskCreateRequest(
            title="飞书初稿",
            conversation_id="conv-1",
            platform_id="lark",
            session_id="lark:group:1",
        )
    )
    case = await engine.create_case(
        name="春节推广", platform_id="lark", session_id="lark:group:1"
    )
    await engine.attach_task(case.case_id, task.task_id)
    view = await engine.get_case_context(case.case_id)
    assert view is not None
    assert view["status"] == "initiated"
    assert len(view["tasks"]) == 1
    assert view["tasks"][0]["title"] == "飞书初稿"
    assert view["event_count"] >= 2  # case_created + task_attached


@pytest.mark.asyncio
async def test_get_case_context_marks_missing_tasks(tmp_path):
    case_store = CaseStore(tmp_path / "cases.db")
    harness_store = HarnessTaskStore(tmp_path / "harness.db")
    engine = CaseEngine(case_store, harness_store=harness_store)
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="sess"
    )
    await engine.attach_task(case.case_id, "ghost-task")
    view = await engine.get_case_context(case.case_id)
    assert view is not None
    assert view["tasks"] == [{"task_id": "ghost-task", "missing": True}]


@pytest.mark.asyncio
async def test_get_case_context_returns_none_for_unknown(engine):
    assert await engine.get_case_context("missing") is None
