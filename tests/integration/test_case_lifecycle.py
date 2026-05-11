"""End-to-end Case lifecycle integration test (W0 Plan A 2A-0).

Walks the canonical happy path from the spec:

    open case → attach 2 tasks → add deliverable → archive

Verifies that Harness Task store stays untouched (Case is layered above,
never re-schemas Harness), the event log captures every transition, and
the archive hook fires exactly once.
"""

from __future__ import annotations

import pytest

from astrbot.core.case import CASE_TERMINAL_STATUSES, CaseEngine, CaseStore
from astrbot.core.harness import (
    HarnessEngine,
    HarnessTaskCreateRequest,
    HarnessTaskStore,
)


@pytest.mark.asyncio
async def test_full_case_lifecycle_open_attach_deliverable_archive(tmp_path):
    case_store = CaseStore(tmp_path / "cases.db")
    harness_store = HarnessTaskStore(tmp_path / "harness.db")
    harness_engine = HarnessEngine(harness_store)

    archive_calls: list[str] = []

    async def archive_hook(case):
        archive_calls.append(case.case_id)

    case_engine = CaseEngine(
        case_store,
        harness_store=harness_store,
        archive_hook=archive_hook,
    )

    # 1) open case ------------------------------------------------------
    case = await case_engine.create_case(
        name="春节KOL推广",
        platform_id="lark",
        session_id="lark:group:kol",
        client_name="客户A",
    )
    assert case.status == "initiated"
    active = await case_engine.get_current_case_for_session("lark:group:kol")
    assert active is not None and active.case_id == case.case_id

    # 2) two harness tasks under the case ------------------------------
    task_a = await harness_engine.create_task(
        HarnessTaskCreateRequest(
            title="飞书 bot 出文案",
            conversation_id="conv-1",
            platform_id="lark",
            session_id="lark:group:kol",
        )
    )
    task_b = await harness_engine.create_task(
        HarnessTaskCreateRequest(
            title="设计师终稿",
            conversation_id="conv-1",
            platform_id="lark",
            session_id="lark:group:kol",
        )
    )
    await case_engine.attach_task(case.case_id, task_a.task_id)
    await case_engine.attach_task(case.case_id, task_b.task_id)

    # 3) deliverable + role + version ---------------------------------
    await case_engine.add_deliverable(
        case.case_id,
        kind="text",
        path="data/kol_draft_v1.md",
        version=1,
    )
    await case_engine.add_deliverable(
        case.case_id,
        kind="image",
        path="data/kol_visual_v1.png",
        version=1,
    )
    await case_engine.assign_role(case.case_id, "业务", "u-biz-001")
    await case_engine.assign_role(case.case_id, "设计", "u-des-001")
    await case_engine.bump_version(case.case_id)
    await case_engine.set_status(case.case_id, "drafting")

    # 4) aggregated context view shows everything ---------------------
    view = await case_engine.get_case_context(case.case_id)
    assert view is not None
    assert view["status"] == "drafting"
    assert view["version"] == 2
    assert sorted(view["task_ids"]) == sorted([task_a.task_id, task_b.task_id])
    assert {t["title"] for t in view["tasks"]} == {"飞书 bot 出文案", "设计师终稿"}
    assert {d["kind"] for d in view["deliverables"]} == {"text", "image"}
    assert view["roles"] == {"业务": "u-biz-001", "设计": "u-des-001"}

    # 5) archive ------------------------------------------------------
    archived = await case_engine.archive_case(case.case_id)
    assert archived.status == "archived"
    assert archived.status in CASE_TERMINAL_STATUSES
    assert archive_calls == [case.case_id]

    # 6) post-archive: no longer the active case for the session ------
    assert (
        await case_engine.get_current_case_for_session("lark:group:kol") is None
    )

    # 7) event log captures every transition --------------------------
    events = await case_store.list_events(case.case_id)
    event_types = [e.event_type for e in events]
    expected_subset = {
        "case_created",
        "task_attached",
        "deliverable_added",
        "role_assigned",
        "version_bumped",
        "status_changed",
        "archived",
    }
    assert expected_subset.issubset(set(event_types))

    # 8) Harness store stayed untouched as a separate sidecar ---------
    harness_a = await harness_store.get_task(task_a.task_id)
    harness_b = await harness_store.get_task(task_b.task_id)
    assert harness_a is not None and harness_a.status == "pending"
    assert harness_b is not None and harness_b.status == "pending"
