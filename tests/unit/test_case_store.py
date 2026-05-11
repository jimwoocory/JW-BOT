"""Unit tests for ``astrbot.core.case.case_store.CaseStore``.

Covers schema bootstrap, CRUD round-trips, JSON-column round-trips, the
session/active-case lookup, and the append-only event log.
"""

from __future__ import annotations

import sqlite3

import pytest

from astrbot.core.case import CaseStore


# ---------------------------------------------------------------------------
# initialize / schema
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_creates_both_tables(tmp_path):
    db_path = tmp_path / "cases.db"
    store = CaseStore(db_path)
    await store.initialize()
    assert db_path.exists()

    with sqlite3.connect(db_path) as raw:
        tables = {
            row[0]
            for row in raw.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "cases" in tables
    assert "case_events" in tables


@pytest.mark.asyncio
async def test_initialize_is_idempotent(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    await store.initialize()
    await store.initialize()
    case = await store.create_case(
        name="round trip", platform_id="qq", session_id="s1"
    )
    assert case.case_id


# ---------------------------------------------------------------------------
# create_case
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_case_seeds_defaults(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(
        name="春节推广",
        platform_id="lark",
        session_id="lark:group:42",
        client_name="客户A",
    )
    assert case.status == "initiated"
    assert case.task_ids == []
    assert case.deliverables == []
    assert case.roles == {}
    assert case.version == 1
    assert case.client_name == "客户A"


@pytest.mark.asyncio
async def test_create_case_emits_case_created_event(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(name="x", platform_id="qq", session_id="s1")
    events = await store.list_events(case.case_id)
    assert len(events) == 1
    assert events[0].event_type == "case_created"
    assert events[0].payload["name"] == "x"


# ---------------------------------------------------------------------------
# get_case / list_cases_for_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_case_returns_none_for_unknown(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    await store.initialize()
    assert await store.get_case("nonexistent") is None


@pytest.mark.asyncio
async def test_list_cases_for_session_orders_by_updated_at_desc(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    a = await store.create_case(name="a", platform_id="qq", session_id="sess")
    b = await store.create_case(name="b", platform_id="qq", session_id="sess")
    # Mutate a so its updated_at moves forward.
    await store.update_case_fields(
        a.case_id,
        roles={"业务": "u1"},
        event_type="role_assigned",
        event_payload={"role": "业务", "user_id": "u1"},
    )
    cases = await store.list_cases_for_session("sess", limit=10)
    assert [c.case_id for c in cases][0] == a.case_id
    assert {c.case_id for c in cases} == {a.case_id, b.case_id}


@pytest.mark.asyncio
async def test_list_cases_for_session_filters_by_status(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    a = await store.create_case(name="a", platform_id="qq", session_id="sess")
    b = await store.create_case(name="b", platform_id="qq", session_id="sess")
    await store.update_case_fields(
        b.case_id,
        status="archived",
        event_type="archived",
        event_payload={"from": "initiated"},
    )
    only_active = await store.list_cases_for_session(
        "sess", statuses=("initiated",)
    )
    assert {c.case_id for c in only_active} == {a.case_id}


# ---------------------------------------------------------------------------
# get_active_case_for_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_active_case_excludes_archived_and_cancelled(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    archived = await store.create_case(
        name="old", platform_id="qq", session_id="sess"
    )
    await store.update_case_fields(
        archived.case_id,
        status="archived",
        event_type="archived",
        event_payload={"from": "initiated"},
    )
    fresh = await store.create_case(name="new", platform_id="qq", session_id="sess")
    active = await store.get_active_case_for_session("sess")
    assert active is not None
    assert active.case_id == fresh.case_id


@pytest.mark.asyncio
async def test_active_case_returns_none_when_no_active(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(name="x", platform_id="qq", session_id="sess")
    await store.update_case_fields(
        case.case_id,
        status="cancelled",
        event_type="status_changed",
        event_payload={"from": "initiated", "to": "cancelled"},
    )
    assert await store.get_active_case_for_session("sess") is None


# ---------------------------------------------------------------------------
# update_case_fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_case_fields_records_event(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(name="x", platform_id="qq", session_id="sess")
    await store.update_case_fields(
        case.case_id,
        task_ids=["t1"],
        event_type="task_attached",
        event_payload={"task_id": "t1"},
    )
    events = await store.list_events(case.case_id)
    assert {e.event_type for e in events} == {"case_created", "task_attached"}


@pytest.mark.asyncio
async def test_update_case_fields_partial_updates_keep_other_columns(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(name="x", platform_id="qq", session_id="sess")
    await store.update_case_fields(
        case.case_id,
        task_ids=["t1"],
        event_type="task_attached",
        event_payload={"task_id": "t1"},
    )
    again = await store.update_case_fields(
        case.case_id,
        roles={"设计": "u9"},
        event_type="role_assigned",
        event_payload={"role": "设计", "user_id": "u9"},
    )
    # task_ids preserved across the second update
    assert again.task_ids == ["t1"]
    assert again.roles == {"设计": "u9"}


@pytest.mark.asyncio
async def test_update_case_fields_raises_for_unknown(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    await store.initialize()
    with pytest.raises(LookupError):
        await store.update_case_fields(
            "missing",
            status="archived",
            event_type="archived",
            event_payload={},
        )


# ---------------------------------------------------------------------------
# append_event / list_events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_append_event_persists_payload(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(name="x", platform_id="qq", session_id="sess")
    await store.append_event(case.case_id, "custom", {"foo": "bar"})
    events = await store.list_events(case.case_id)
    assert any(e.event_type == "custom" and e.payload == {"foo": "bar"} for e in events)


@pytest.mark.asyncio
async def test_list_events_returns_chronological_order(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(name="x", platform_id="qq", session_id="sess")
    await store.append_event(case.case_id, "evt1", {"i": 1})
    await store.append_event(case.case_id, "evt2", {"i": 2})
    events = await store.list_events(case.case_id)
    assert [e.event_type for e in events] == ["case_created", "evt1", "evt2"]


# ---------------------------------------------------------------------------
# JSON column round-trips
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unicode_round_trip_through_json_columns(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(
        name="春节推广 🎉",
        platform_id="lark",
        session_id="lark:group:春节",
        client_name="客户·A",
    )
    fetched = await store.get_case(case.case_id)
    assert fetched is not None
    assert fetched.name == "春节推广 🎉"
    assert fetched.client_name == "客户·A"
    assert fetched.session_id == "lark:group:春节"


@pytest.mark.asyncio
async def test_payload_round_trip_preserves_nested_dict(tmp_path):
    store = CaseStore(tmp_path / "cases.db")
    case = await store.create_case(
        name="x",
        platform_id="qq",
        session_id="sess",
        payload={"client_meta": {"industry": "fashion"}, "tags": ["热点", "春节"]},
    )
    fetched = await store.get_case(case.case_id)
    assert fetched is not None
    assert fetched.payload["client_meta"]["industry"] == "fashion"
    assert fetched.payload["tags"] == ["热点", "春节"]
