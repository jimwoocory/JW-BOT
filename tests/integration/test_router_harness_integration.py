"""
Router 集成测试 — Router 与 Harness 的集成验证。

Task 2 — 验证 SessionRouter 与 Harness 的集成，以及端到端流程。
"""
import asyncio

import pytest

from astrbot.plugins.hermes_bridge.router import (
    SessionRouter,
    PlatformUser,
    PlatformType,
)
from astrbot.core.harness import (
    HarnessEngine,
    HarnessMemoryStore,
    HarnessTaskCreateRequest,
    HarnessTaskStore,
)


@pytest.fixture
def session_router(tmp_path):
    db = tmp_path / "session_router.db"
    return SessionRouter(str(db))


# ============================================================================
# Section 1: Router → Harness 流程集成
# ============================================================================


@pytest.mark.asyncio
async def test_platform_user_to_harness_task(session_router, tmp_path):
    """平台用户通过 Router 创建 session_id，再创建 Harness 任务。"""
    # 1. Router 创建/获取会话
    user = PlatformUser(platform=PlatformType.QQ, user_id="integration_user_1")
    session_id = session_router.get_or_create_session(user)
    assert len(session_id) == 12

    # 2. 使用 session_id 创建 Harness 任务
    task_store = HarnessTaskStore(tmp_path / "harness_tasks.db")
    engine = HarnessEngine(task_store)
    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="集成测试任务",
            conversation_id=f"conv-{session_id}",
            platform_id="qq",
            session_id=f"qq:{user.user_id}",
            payload={},
        )
    )
    assert task.status == "pending"
    assert task.session_id == f"qq:{user.user_id}"


@pytest.mark.asyncio
async def test_same_user_gets_same_session_id(session_router, tmp_path):
    """同一平台用户多次路由应使用同一 session_id。"""
    user = PlatformUser(platform=PlatformType.TELEGRAM, user_id="repeat_user")
    sid1 = session_router.get_or_create_session(user)
    sid2 = session_router.get_or_create_session(user)
    assert sid1 == sid2

    # 两次创建的任务应关联到同一会话
    task_store = HarnessTaskStore(tmp_path / "harness_tasks.db")
    engine = HarnessEngine(task_store)
    task1 = await engine.create_task(
        HarnessTaskCreateRequest(
            title="任务 A",
            conversation_id=f"conv-{sid1}",
            platform_id="telegram",
            session_id=f"telegram:{user.user_id}",
            payload={},
        )
    )
    task2 = await engine.create_task(
        HarnessTaskCreateRequest(
            title="任务 B",
            conversation_id=f"conv-{sid2}",
            platform_id="telegram",
            session_id=f"telegram:{user.user_id}",
            payload={},
        )
    )
    assert task1.session_id == task2.session_id


@pytest.mark.asyncio
async def test_multi_platform_users_isolated(session_router, tmp_path):
    """不同平台用户的 session_id 和任务应相互隔离。"""
    users = [
        PlatformUser(platform=PlatformType.QQ, user_id="user_qq"),
        PlatformUser(platform=PlatformType.DISCORD, user_id="user_discord"),
        PlatformUser(platform=PlatformType.WEBUI, user_id="user_web"),
    ]
    sessions = [session_router.get_or_create_session(u) for u in users]
    # 所有 session_id 应不同
    assert len(set(sessions)) == 3

    # 各自创建任务
    task_store = HarnessTaskStore(tmp_path / "harness_tasks.db")
    engine = HarnessEngine(task_store)
    for i, (user, sid) in enumerate(zip(users, sessions)):
        task = await engine.create_task(
            HarnessTaskCreateRequest(
                title=f"平台{i}任务",
                conversation_id=f"conv-{sid}",
                platform_id=user.platform.value,
                session_id=user.generate_id(),
                payload={},
            )
        )
        assert task.session_id == user.generate_id()


# ============================================================================
# Section 2: 多次交互一致性
# ============================================================================


@pytest.mark.asyncio
async def test_user_says_task_then_list(session_router, tmp_path):
    """先创建任务，再列出任务。"""
    user = PlatformUser(platform=PlatformType.QQ, user_id="flow_user")
    session_id = session_router.get_or_create_session(user)

    task_store = HarnessTaskStore(tmp_path / "harness_tasks.db")
    engine = HarnessEngine(task_store)

    # 创建任务
    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="测试任务",
            conversation_id=f"conv-{session_id}",
            platform_id="qq",
            session_id=user.generate_id(),
            payload={"workflow_kind": "general"},
        )
    )
    assert task.status == "pending"

    # 列出任务（通过 task_store）
    tasks = await task_store.list_tasks_for_conversation(f"conv-{session_id}")
    assert len(tasks) >= 1
    assert any(t.task_id == task.task_id for t in tasks)


@pytest.mark.asyncio
async def test_task_completeness_flow(session_router, tmp_path):
    """任务从创建 → 完成的完整流程。"""
    user = PlatformUser(platform=PlatformType.WEBUI, user_id="complete_user")
    session_id = session_router.get_or_create_session(user)

    task_store = HarnessTaskStore(tmp_path / "harness_tasks.db")
    memory_store = HarnessMemoryStore(tmp_path / "harness_memory.db")
    engine = HarnessEngine(task_store)
    conversation_id = f"conv-{session_id}"

    # 1. 创建
    task = await engine.create_task(
        HarnessTaskCreateRequest(
            title="完整流程任务",
            conversation_id=conversation_id,
            platform_id="webui",
            session_id=user.generate_id(),
            payload={},
        )
    )
    assert task.status == "pending"

    # 2. 完成
    await engine.complete_task(
        task.task_id, result={"summary": "任务已完成"}
    )

    # 3. 验证状态（通过 task_store 查询）
    tasks = await task_store.list_tasks_for_conversation(conversation_id)
    completed = [t for t in tasks if t.task_id == task.task_id]
    assert len(completed) == 1
    assert completed[0].status == "completed"


# ============================================================================
# Section 3: 边缘集成场景
# ============================================================================


@pytest.mark.asyncio
async def test_session_deleted_then_recreate(session_router, tmp_path):
    """删除会话后重新路由应创建新 session_id。"""
    user = PlatformUser(platform=PlatformType.QQ, user_id="recreate_user")
    sid1 = session_router.get_or_create_session(user)

    # 删除会话
    session_router.delete_session(sid1)

    # 重新获取应创建新的 session_id
    sid2 = session_router.get_or_create_session(user)
    assert sid1 != sid2


@pytest.mark.asyncio
async def test_rapid_concurrent_sessions(session_router, tmp_path):
    """快速连续创建多个不同用户的会话和任务。"""
    users = [
        PlatformUser(platform=PlatformType.QQ, user_id=f"rapid_{i}")
        for i in range(10)
    ]
    sessions = [session_router.get_or_create_session(u) for u in users]

    task_store = HarnessTaskStore(tmp_path / "harness_tasks.db")
    engine = HarnessEngine(task_store)

    async def make_task(user, sid, i):
        return await engine.create_task(
            HarnessTaskCreateRequest(
                title=f"快速任务{i}",
                conversation_id=f"conv-{sid}",
                platform_id="qq",
                session_id=user.generate_id(),
                payload={},
            )
        )

    coros = [make_task(u, s, i) for i, (u, s) in enumerate(zip(users, sessions))]
    results = await asyncio.gather(*coros)
    assert len(results) == 10
    # 所有任务 session_id 不同
    session_ids = [t.session_id for t in results]
    assert len(set(session_ids)) == 10
