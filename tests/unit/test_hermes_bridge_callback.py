"""单测：astrbot/core/hermes_callback_dispatcher.py + hermes_dlq_logger.py

覆盖（G2 验收清单）：
- 正常回群成功（首次成功 / 中途重试后成功）
- 5xx / 网络异常：重试 3 次后写 DLQ
- 4xx / Permanent：不重试、直接 DLQ
- DLQ 文件超过 max_bytes 时的单备份轮转
- HMAC X-Hub-Signature-256 校验
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

import pytest

from astrbot.core.hermes_callback_dispatcher import (
    HermesCallbackDispatcher,
    PermanentSendError,
    RetriableSendError,
    SendOutcome,
    classify_http_status,
    verify_hmac_signature,
)
from astrbot.core.hermes_dlq_logger import (
    HermesDLQLogger,
    build_dlq_record,
)


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def dlq_path(tmp_path):
    return tmp_path / "hermes_dlq.jsonl"


@pytest.fixture
def dlq_logger(dlq_path):
    return HermesDLQLogger(dlq_path)


def _instant_sleep_factory():
    """返回不实际睡眠的 sleep 替身，便于测试时间敏感的重试。"""

    async def _sleep(_delay: float) -> None:  # noqa: ARG001
        return None

    return _sleep


# ── 正常回群成功 ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_success_first_attempt(dlq_logger, dlq_path):
    seen = []

    async def sender(umo, msg):
        seen.append((umo, msg))

    disp = HermesCallbackDispatcher(
        sender=sender,
        dlq_logger=dlq_logger,
        sleep=_instant_sleep_factory(),
    )
    outcome = await disp.send_with_retry(
        target_umo="qq:GroupMessage:1_2",
        message="hi",
        task_id="t1",
    )
    assert outcome == SendOutcome(
        success=True, attempts=1, last_error=None, dlq_written=False
    )
    assert seen == [("qq:GroupMessage:1_2", "hi")]
    assert not dlq_path.exists() or dlq_path.read_text() == ""


@pytest.mark.asyncio
async def test_send_recovers_after_one_retriable_error(dlq_logger, dlq_path):
    """第一次抛 Retriable，第二次成功 → 视为整体成功，不写 DLQ。"""
    attempts: list[int] = []

    async def sender(umo, msg):  # noqa: ARG001
        attempts.append(1)
        if len(attempts) < 2:
            raise RetriableSendError("upstream 503")

    disp = HermesCallbackDispatcher(
        sender=sender,
        dlq_logger=dlq_logger,
        sleep=_instant_sleep_factory(),
    )
    outcome = await disp.send_with_retry(target_umo="lark:foo", message="x")
    assert outcome.success is True
    assert outcome.attempts == 2
    assert outcome.dlq_written is False
    assert not dlq_path.exists() or dlq_path.read_text() == ""


# ── 5xx 重试 3 次后写 DLQ ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_5xx_retried_three_times_then_dlq(dlq_logger, dlq_path):
    call_count = 0
    sleep_calls: list[float] = []

    async def sender(umo, msg):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        raise RetriableSendError("HTTP 503 Service Unavailable")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    disp = HermesCallbackDispatcher(
        sender=sender,
        dlq_logger=dlq_logger,
        max_attempts=3,
        retry_delays=(1.0, 2.0, 4.0),
        sleep=fake_sleep,
    )
    outcome = await disp.send_with_retry(
        target_umo="qq:1",
        message="payload",
        task_id="task-5xx",
        extra_payload={"session_key": "sk-1"},
    )

    assert outcome.success is False
    assert outcome.attempts == 3
    assert outcome.dlq_written is True
    assert outcome.last_error and "retriable" in outcome.last_error
    assert call_count == 3
    # 退避：在 attempt 1 / 2 后 sleep，attempt 3 失败后直接落 DLQ 不再 sleep
    assert sleep_calls == [1.0, 2.0]

    # DLQ 记录
    lines = dlq_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["task_id"] == "task-5xx"
    assert rec["target_umo"] == "qq:1"
    assert rec["payload"]["message"] == "payload"
    assert rec["payload"]["session_key"] == "sk-1"
    assert rec["attempt_count"] == 3
    assert "retriable" in rec["last_error"]


# ── 4xx：不重试，直接 DLQ ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_4xx_permanent_no_retry_direct_dlq(dlq_logger, dlq_path):
    call_count = 0
    sleep_calls: list[float] = []

    async def sender(umo, msg):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        raise PermanentSendError("HTTP 404 Not Found")

    async def fake_sleep(delay: float):
        sleep_calls.append(delay)

    disp = HermesCallbackDispatcher(
        sender=sender,
        dlq_logger=dlq_logger,
        max_attempts=3,
        sleep=fake_sleep,
    )
    outcome = await disp.send_with_retry(
        target_umo="qq:2", message="msg", task_id="task-4xx"
    )
    assert outcome.success is False
    assert outcome.attempts == 1
    assert outcome.dlq_written is True
    assert outcome.last_error and "permanent" in outcome.last_error
    assert call_count == 1
    assert sleep_calls == []

    rec = json.loads(dlq_path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["attempt_count"] == 1
    assert rec["task_id"] == "task-4xx"
    assert "permanent" in rec["last_error"]


@pytest.mark.asyncio
async def test_unknown_exception_treated_as_permanent(dlq_logger, dlq_path):
    """陌生异常应当被视为 permanent，立即 DLQ 而非无尽重试。"""

    class _Boom(Exception):
        pass

    async def sender(umo, msg):  # noqa: ARG001
        raise _Boom("kaboom")

    disp = HermesCallbackDispatcher(
        sender=sender, dlq_logger=dlq_logger, sleep=_instant_sleep_factory()
    )
    outcome = await disp.send_with_retry(target_umo="qq:9", message="m")
    assert outcome.success is False
    assert outcome.attempts == 1
    assert outcome.dlq_written is True
    assert "unknown" in (outcome.last_error or "")
    assert dlq_path.exists()


# ── DLQ 轮转 ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dlq_rotation_when_exceeds_max_bytes(tmp_path):
    """超出 max_bytes 时应轮转到 .1 备份并开新文件。"""
    path = tmp_path / "hermes_dlq.jsonl"
    dlq = HermesDLQLogger(path, max_bytes=200)

    for i in range(10):
        await dlq.log(
            build_dlq_record(
                task_id=f"t{i}",
                target_umo="qq:1",
                payload={"message": "x" * 60},
                last_error="permanent: 4xx",
                attempt_count=1,
            )
        )

    backup = path.with_name("hermes_dlq.jsonl.1")
    assert backup.exists(), "轮转后应产生 .1 备份"
    assert path.exists(), "主文件应继续写入"
    # 主文件大小允许略超（单条记录可能 > max_bytes），但有上限
    assert path.stat().st_size <= 200 + 200


@pytest.mark.asyncio
async def test_dlq_second_rotation_overwrites_backup(tmp_path):
    path = tmp_path / "hermes_dlq.jsonl"
    dlq = HermesDLQLogger(path, max_bytes=120)

    for i in range(40):
        await dlq.log(
            build_dlq_record(
                task_id=f"t{i}",
                target_umo="qq:1",
                payload={"msg": "y" * 30},
                last_error="x",
                attempt_count=1,
            )
        )

    backup = path.with_name("hermes_dlq.jsonl.1")
    assert backup.exists()
    # 二次轮转后旧 .1 被覆盖，不允许无限增长
    assert backup.stat().st_size <= 240


@pytest.mark.asyncio
async def test_dlq_concurrent_writes_no_loss(tmp_path):
    path = tmp_path / "hermes_dlq.jsonl"
    dlq = HermesDLQLogger(path)
    n = 30
    await asyncio.gather(
        *(
            dlq.log(
                build_dlq_record(
                    task_id=f"t{i}",
                    target_umo="qq",
                    payload={"i": i},
                    last_error="e",
                    attempt_count=1,
                )
            )
            for i in range(n)
        )
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == n


@pytest.mark.asyncio
async def test_dlq_non_serializable_record_skipped_silently(tmp_path):
    path = tmp_path / "hermes_dlq.jsonl"
    dlq = HermesDLQLogger(path)
    # set() 不可 JSON 序列化 → 应静默跳过，不抛异常
    await dlq.log({"bad": {1, 2, 3}})
    assert not path.exists() or path.read_text() == ""


# ── HMAC 签名校验 ─────────────────────────────────────────────────────────────


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_hmac_verify_accepts_correct_signature():
    body = b'{"task_id":"t","message":"hello"}'
    sig = _sign("secret-key", body)
    assert verify_hmac_signature("secret-key", body, sig) is True


def test_hmac_verify_rejects_wrong_secret():
    body = b'{"a":1}'
    sig = _sign("real-secret", body)
    assert verify_hmac_signature("wrong-secret", body, sig) is False


def test_hmac_verify_rejects_tampered_body():
    body = b'{"a":1}'
    sig = _sign("k", body)
    assert verify_hmac_signature("k", b'{"a":2}', sig) is False


def test_hmac_verify_rejects_missing_prefix():
    body = b'{"a":1}'
    raw_hex = hmac.new(b"k", body, hashlib.sha256).hexdigest()
    assert verify_hmac_signature("k", body, raw_hex) is False  # 缺少 "sha256="


def test_hmac_verify_rejects_empty_inputs():
    body = b'{"a":1}'
    sig = _sign("k", body)
    assert verify_hmac_signature("", body, sig) is False
    assert verify_hmac_signature("k", body, "") is False
    assert verify_hmac_signature("k", body, "sha256=") is False


# ── http status 分类辅助 ──────────────────────────────────────────────────────


def test_classify_http_status():
    assert classify_http_status(500) is RetriableSendError
    assert classify_http_status(502) is RetriableSendError
    assert classify_http_status(599) is RetriableSendError
    assert classify_http_status(400) is PermanentSendError
    assert classify_http_status(404) is PermanentSendError
    assert classify_http_status(499) is PermanentSendError
    assert classify_http_status(200) is None
    assert classify_http_status(301) is None


# ── dispatcher 入参校验 ───────────────────────────────────────────────────────


def test_dispatcher_rejects_zero_max_attempts(dlq_logger):
    async def _noop(*_a, **_k):
        return None

    with pytest.raises(ValueError):
        HermesCallbackDispatcher(sender=_noop, dlq_logger=dlq_logger, max_attempts=0)


@pytest.mark.asyncio
async def test_dispatcher_default_delays_indexing(dlq_logger):
    """retry_delays 超出长度时应取最后一项（防越界）。"""
    used_delays: list[float] = []

    async def sender(*_a, **_k):
        raise RetriableSendError("x")

    async def fake_sleep(d: float):
        used_delays.append(d)

    disp = HermesCallbackDispatcher(
        sender=sender,
        dlq_logger=dlq_logger,
        max_attempts=5,
        retry_delays=(0.1, 0.2),  # 仅两项，attempt 3/4 应复用 0.2
        sleep=fake_sleep,
    )
    await disp.send_with_retry(target_umo="qq:x", message="m")
    assert used_delays == [0.1, 0.2, 0.2, 0.2]
