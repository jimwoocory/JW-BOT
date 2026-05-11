"""端到端集成测试：Hermes Webhook → plugin handler → platform adapter / DLQ

针对两份 plugin 文件参数化运行：
  - v1: astrbot/plugins/hermes_bridge/__init__.py    (git-tracked, 已归档)
  - v2: data/plugins/hermes_bridge/hermes_bridge.py  (生产部署，未 git 追踪)

配合 mock context.send_message，使用 aiohttp TestServer 启动 webhook 端点，
然后发起带 HMAC 签名的 HTTP POST 请求，验证：

- 平台 send 成功 → 200 OK，消息成功投递（无 DLQ 写入）
- 平台始终失败（retriable）→ 202 queued_to_dlq，DLQ 文件有记录
- HMAC 签名错误 → 401
- 缺 umo → 202 queued_to_dlq，DLQ 文件有记录

不依赖完整的 Star 框架启动；仅 stub Context 暴露 get_config / send_message。
若 v2 文件不存在（CI / 干净 checkout）则该参数化分支自动 skip。
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# v2 plugin 文件路径（部署位置，未 git 追踪）
V2_PLUGIN_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "plugins"
    / "hermes_bridge"
    / "hermes_bridge.py"
)


def _load_v2_plugin_cls():
    if not V2_PLUGIN_FILE.exists():
        return None
    spec = importlib.util.spec_from_file_location(
        "hermes_bridge_v2_test", V2_PLUGIN_FILE
    )
    assert spec and spec.loader, "Cannot create spec for v2 plugin"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.HermesBridgePlugin


def _load_v1_plugin_cls():
    from astrbot.plugins.hermes_bridge import HermesBridgePlugin as V1Plugin

    return V1Plugin


# 参数化两份实装；v2 缺失时 fixture 自动 skip
_V1_CLS = _load_v1_plugin_cls()
_V2_CLS = _load_v2_plugin_cls()

PLUGIN_VARIANTS = [pytest.param(_V1_CLS, id="v1")]
if _V2_CLS is not None:
    PLUGIN_VARIANTS.append(pytest.param(_V2_CLS, id="v2"))


# ── fixtures ─────────────────────────────────────────────────────────────────


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _make_context(
    *,
    tmp_path: Path,
    send_message_behavior,
):
    """构造一个最小可用的 mock Context。

    send_message_behavior:
        - 'success'     : context.send_message 返回 True
        - 'returns_false': 返回 False（→ Permanent）
        - 'raises_timeout': raise asyncio.TimeoutError（→ Retriable）
        - 'raises_value': raise ValueError（→ unknown / permanent）
    """
    ctx = MagicMock()
    ctx.get_config.return_value = {
        "hermes_bridge": {
            "webhook_url": "http://localhost:1/none",
            "task_webhook_url": "http://localhost:1/none",
            "secret": "test-secret",
            "response_port": 0,  # 不启动 server
            "data_dir": str(tmp_path),
            "allowed_platforms": [],
            "excluded_platforms": [],
            "direct_chat_enabled": False,
            "topic_workflow_enabled": False,
        }
    }
    ctx.harness_engine = None
    ctx.harness_store = None

    if send_message_behavior == "success":
        ctx.send_message = AsyncMock(return_value=True)
    elif send_message_behavior == "returns_false":
        ctx.send_message = AsyncMock(return_value=False)
    elif send_message_behavior == "raises_timeout":
        ctx.send_message = AsyncMock(side_effect=asyncio.TimeoutError())
    elif send_message_behavior == "raises_value":
        ctx.send_message = AsyncMock(side_effect=ValueError("boom"))
    else:
        raise ValueError(f"unknown behavior {send_message_behavior}")
    return ctx


async def _build_app_with_plugin(plugin) -> web.Application:
    app = web.Application()
    app.router.add_post("/hermes_response", plugin._handle_hermes_response)
    return app


def _make_plugin(plugin_cls, tmp_path, behavior):
    ctx = _make_context(tmp_path=tmp_path, send_message_behavior=behavior)
    plugin = plugin_cls(ctx)
    # 关掉真实 retry sleep 加速测试
    plugin._callback_dispatcher._sleep = AsyncMock(return_value=None)
    return plugin


# ── tests ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("plugin_cls", PLUGIN_VARIANTS)
@pytest.mark.asyncio
async def test_callback_success_routes_to_platform(plugin_cls, tmp_path):
    """正常路径：HMAC 签名有效 + send_message 成功 → 200 + 平台收到。"""
    plugin = _make_plugin(plugin_cls, tmp_path, "success")
    app = await _build_app_with_plugin(plugin)
    async with TestClient(TestServer(app)) as client:
        body = json.dumps(
            {
                "task_id": "t-success",
                "message": "Hermes 回答内容",
                "unified_msg_origin": "qq:GroupMessage:1_2",
            }
        ).encode("utf-8")
        sig = _sign("test-secret", body)
        resp = await client.post(
            "/hermes_response",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sig,
            },
        )
        assert resp.status == 200
        payload = await resp.json()
        assert payload["status"] == "ok"
        assert payload["umo"] == "qq:GroupMessage:1_2"
        assert payload["attempts"] == 1

    plugin.context.send_message.assert_awaited_once()
    args, _ = plugin.context.send_message.call_args
    assert args[0] == "qq:GroupMessage:1_2"
    dlq = tmp_path / "hermes_dlq.jsonl"
    assert not dlq.exists() or dlq.read_text() == ""


@pytest.mark.parametrize("plugin_cls", PLUGIN_VARIANTS)
@pytest.mark.asyncio
async def test_callback_retriable_failures_drain_to_dlq(plugin_cls, tmp_path):
    """端到端：send_message 持续 timeout（5xx-like）→ 3 次后写 DLQ。"""
    plugin = _make_plugin(plugin_cls, tmp_path, "raises_timeout")
    app = await _build_app_with_plugin(plugin)
    async with TestClient(TestServer(app)) as client:
        body = json.dumps(
            {
                "task_id": "t-retry",
                "message": "需要回群",
                "unified_msg_origin": "qq:Group:3_4",
                "session_key": "sk-X",
            }
        ).encode("utf-8")
        sig = _sign("test-secret", body)
        resp = await client.post(
            "/hermes_response",
            data=body,
            headers={"X-Hub-Signature-256": sig},
        )
        assert resp.status == 202
        payload = await resp.json()
        assert payload["status"] == "queued_to_dlq"
        assert payload["attempts"] == 3
        assert payload["dlq_written"] is True

    assert plugin.context.send_message.await_count == 3

    dlq = tmp_path / "hermes_dlq.jsonl"
    assert dlq.exists(), "DLQ 文件应被创建"
    rec = json.loads(dlq.read_text(encoding="utf-8").splitlines()[0])
    assert rec["task_id"] == "t-retry"
    assert rec["target_umo"] == "qq:Group:3_4"
    assert rec["payload"]["session_key"] == "sk-X"
    assert rec["attempt_count"] == 3
    assert "retriable" in rec["last_error"]


@pytest.mark.parametrize("plugin_cls", PLUGIN_VARIANTS)
@pytest.mark.asyncio
async def test_callback_send_returns_false_is_permanent(plugin_cls, tmp_path):
    """context.send_message 返回 False → Permanent，不重试，直接 DLQ。"""
    plugin = _make_plugin(plugin_cls, tmp_path, "returns_false")
    app = await _build_app_with_plugin(plugin)
    async with TestClient(TestServer(app)) as client:
        body = json.dumps(
            {
                "task_id": "t-perm",
                "message": "msg",
                "unified_msg_origin": "lark:foo:bar",
            }
        ).encode("utf-8")
        sig = _sign("test-secret", body)
        resp = await client.post(
            "/hermes_response",
            data=body,
            headers={"X-Hub-Signature-256": sig},
        )
        assert resp.status == 202
        payload = await resp.json()
        assert payload["status"] == "queued_to_dlq"
        assert payload["attempts"] == 1
        assert payload["dlq_written"] is True

    assert plugin.context.send_message.await_count == 1

    dlq = tmp_path / "hermes_dlq.jsonl"
    rec = json.loads(dlq.read_text(encoding="utf-8").splitlines()[0])
    assert rec["attempt_count"] == 1
    assert "permanent" in rec["last_error"]


@pytest.mark.parametrize("plugin_cls", PLUGIN_VARIANTS)
@pytest.mark.asyncio
async def test_callback_bad_hmac_returns_401(plugin_cls, tmp_path):
    """HMAC 签名错误 → 401，不进入处理逻辑、不写 DLQ、不调用 send_message。"""
    plugin = _make_plugin(plugin_cls, tmp_path, "success")
    app = await _build_app_with_plugin(plugin)
    async with TestClient(TestServer(app)) as client:
        body = json.dumps({"message": "x", "unified_msg_origin": "qq:1"}).encode("utf-8")
        resp = await client.post(
            "/hermes_response",
            data=body,
            headers={"X-Hub-Signature-256": "sha256=deadbeef"},
        )
        assert resp.status == 401
        payload = await resp.json()
        assert payload["status"] == "unauthorized"

    plugin.context.send_message.assert_not_called()
    dlq = tmp_path / "hermes_dlq.jsonl"
    assert not dlq.exists() or dlq.read_text() == ""


@pytest.mark.parametrize("plugin_cls", PLUGIN_VARIANTS)
@pytest.mark.asyncio
async def test_callback_missing_umo_writes_to_dlq(plugin_cls, tmp_path):
    """没有 umo 又找不到回传地址 → 202 + DLQ。"""
    plugin = _make_plugin(plugin_cls, tmp_path, "success")
    app = await _build_app_with_plugin(plugin)
    async with TestClient(TestServer(app)) as client:
        body = json.dumps({"message": "x", "session_key": "no-such-session"}).encode(
            "utf-8"
        )
        sig = _sign("test-secret", body)
        resp = await client.post(
            "/hermes_response",
            data=body,
            headers={"X-Hub-Signature-256": sig},
        )
        assert resp.status == 202
        payload = await resp.json()
        assert payload["status"] == "queued_to_dlq"
        assert payload["reason"] == "umo_not_found"

    plugin.context.send_message.assert_not_called()
    dlq = tmp_path / "hermes_dlq.jsonl"
    assert dlq.exists()
    rec = json.loads(dlq.read_text(encoding="utf-8").splitlines()[0])
    assert rec["target_umo"] is None
    assert rec["last_error"] == "umo_not_found"
