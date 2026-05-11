"""Unit tests for ``astrbot.builtin_stars.builtin_commands.commands.case``.

These mirror ``test_harness_commands.py`` — wire a real engine + store
through ``MagicMock`` context, drive the command surface, and assert the
side effects in the SQLite sidecar.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from astrbot.builtin_stars.builtin_commands.commands.case import CaseCommands
from astrbot.core.case import CaseEngine, CaseStore
from astrbot.core.harness import HarnessTaskCreateRequest, HarnessTaskStore


def _make_event(umo: str = "qq:friend:1") -> MagicMock:
    event = MagicMock()
    event.unified_msg_origin = umo
    event.get_platform_id.return_value = "qq"
    event.message_str = ""
    return event


def _make_context(case_engine, case_store):
    context = MagicMock()
    context.case_engine = case_engine
    context.case_store = case_store
    return context


# ---------------------------------------------------------------------------
# /case new
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_new_creates_case_in_store(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:99")

    await cmd.case_new(event, "春节推广 --client 客户A")

    cases = await store.list_cases_for_session("qq:friend:99")
    assert len(cases) == 1
    assert cases[0].name == "春节推广"
    assert cases[0].client_name == "客户A"
    event.set_result.assert_called_once()


@pytest.mark.asyncio
async def test_case_new_without_client_flag(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:1")
    await cmd.case_new(event, "干净 case")
    cases = await store.list_cases_for_session("qq:friend:1")
    assert cases[0].client_name is None


@pytest.mark.asyncio
async def test_case_new_rejects_empty_args(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event()
    await cmd.case_new(event, "   ")
    cases = await store.list_cases_for_session("qq:friend:1")
    assert cases == []
    event.set_result.assert_called_once()


@pytest.mark.asyncio
async def test_case_new_reports_when_engine_uninitialized():
    context = MagicMock()
    context.case_engine = None
    context.case_store = None
    cmd = CaseCommands(context)
    event = _make_event()
    await cmd.case_new(event, "anything")
    event.set_result.assert_called_once()


# ---------------------------------------------------------------------------
# /case context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_context_renders_aggregated_view(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    harness_store = HarnessTaskStore(tmp_path / "harness.db")
    engine = CaseEngine(store, harness_store=harness_store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:ctx")

    case = await engine.create_case(
        name="春节推广", platform_id="qq", session_id="qq:friend:ctx"
    )
    task = await harness_store.create_task(
        HarnessTaskCreateRequest(
            title="飞书初稿",
            conversation_id="conv-1",
            platform_id="qq",
            session_id="qq:friend:ctx",
        )
    )
    await engine.attach_task(case.case_id, task.task_id)

    await cmd.case_context(event)

    rendered = event.set_result.call_args.args[0].chain[0].text
    assert "春节推广" in rendered
    assert "飞书初稿" in rendered
    assert "version: 1" in rendered


@pytest.mark.asyncio
async def test_case_context_warns_when_no_active_case(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:empty")
    await cmd.case_context(event)
    rendered = event.set_result.call_args.args[0].chain[0].text
    assert "活跃 case" in rendered


# ---------------------------------------------------------------------------
# /case list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_list_outputs_recent_cases(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:ls")

    await engine.create_case(name="A", platform_id="qq", session_id="qq:friend:ls")
    await engine.create_case(name="B", platform_id="qq", session_id="qq:friend:ls")
    await cmd.case_list(event)
    rendered = event.set_result.call_args.args[0].chain[0].text
    assert "A" in rendered and "B" in rendered


@pytest.mark.asyncio
async def test_case_list_handles_empty_session(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:empty-ls")
    await cmd.case_list(event)
    rendered = event.set_result.call_args.args[0].chain[0].text
    assert "没有 case" in rendered


# ---------------------------------------------------------------------------
# /case attach
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_attach_appends_task_to_active_case(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:attach")

    case = await engine.create_case(
        name="x", platform_id="qq", session_id="qq:friend:attach"
    )
    await cmd.case_attach(event, "task-42")
    refreshed = await store.get_case(case.case_id)
    assert refreshed is not None
    assert refreshed.task_ids == ["task-42"]


@pytest.mark.asyncio
async def test_case_attach_requires_argument(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event()
    await cmd.case_attach(event, "")
    event.set_result.assert_called_once()


# ---------------------------------------------------------------------------
# /case archive + /case status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_archive_marks_status_archived(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:arch")

    case = await engine.create_case(
        name="x", platform_id="qq", session_id="qq:friend:arch"
    )
    await cmd.case_archive(event)
    refreshed = await store.get_case(case.case_id)
    assert refreshed is not None
    assert refreshed.status == "archived"


@pytest.mark.asyncio
async def test_case_status_updates_when_valid(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:status")

    case = await engine.create_case(
        name="x", platform_id="qq", session_id="qq:friend:status"
    )
    await cmd.case_status(event, "drafting")
    refreshed = await store.get_case(case.case_id)
    assert refreshed is not None
    assert refreshed.status == "drafting"


@pytest.mark.asyncio
async def test_case_status_rejects_invalid_value(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    engine = CaseEngine(store)
    cmd = CaseCommands(_make_context(engine, store))
    event = _make_event("qq:friend:status-bad")
    case = await engine.create_case(
        name="x", platform_id="qq", session_id="qq:friend:status-bad"
    )
    await cmd.case_status(event, "totally_made_up")
    refreshed = await store.get_case(case.case_id)
    assert refreshed is not None
    assert refreshed.status == "initiated"
