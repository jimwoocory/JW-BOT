"""
[已归档 - v1.0.0，不再加载]
活跃版本为 data/plugins/hermes_bridge/hermes_bridge.py (v2.0.0)

AstrBot 到 Hermes Agent 的 Webhook 桥接插件（旧版）

旧版消息流：AstrBot 收消息 → SessionRouter → 转发到 Hermes
新版消息流：AstrBot LLM 先处理 → 不满意时 → IntentRouter 升级到 Hermes

G2 / Phase 0.3: 接收 Hermes 回调时通过 HermesCallbackDispatcher 异步回群，
失败按指数退避重试 3 次后落盘到 hermes_dlq.jsonl。此实现与
data/plugins/hermes_bridge/hermes_bridge.py 内的 v2 wiring 等价，作为
git-tracked 的参考实装；部署时若 v2 文件被覆盖，可对照本文件同步。
"""

import asyncio
import hashlib
import hmac
import json
import time
from pathlib import Path

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Plain
from astrbot.api.star import Star
from astrbot.core.hermes_callback_dispatcher import (
    HermesCallbackDispatcher,
    PermanentSendError,
    RetriableSendError,
    classify_http_status,
    verify_hmac_signature,
)
from astrbot.core.hermes_dlq_logger import HermesDLQLogger

from .router import PlatformType, PlatformUser, SessionRouter

# ModelRouter 已删除（2026-04-27），任务分类由 IntentRouter 承接


class HermesBridgePlugin(Star):
    def __init__(self, context):
        super().__init__(context)

        # 从配置加载
        config = context.get_config()
        self.hermes_webhook_url = config.get("hermes_bridge", {}).get(
            "webhook_url", "http://localhost:8644/webhooks/astrbot_qq"
        )
        self.hermes_secret = config.get("hermes_bridge", {}).get(
            "secret", "astrbot-secret-key"
        )
        self.response_port = config.get("hermes_bridge", {}).get("response_port", 8645)

        # 持久化路径：默认仓库 data/ 目录，允许 hermes_bridge.data_dir 覆盖（测试）
        hcfg = config.get("hermes_bridge", {})
        data_dir_override = hcfg.get("data_dir")
        if data_dir_override:
            data_dir = Path(data_dir_override)
            data_dir.mkdir(parents=True, exist_ok=True)
        else:
            data_dir = (
                Path(context.get_config_path()).parent.parent / "data"
            )
        self.session_router = SessionRouter(str(data_dir / "hermes_sessions.db"))

        # session_key → unified_msg_origin 的内存缓存（重启后由首条消息重建）
        self._umo_cache: dict[str, str] = {}

        # 回群链路 DLQ + 重试调度器（G2 / Phase 0.3）
        self._dlq_logger = HermesDLQLogger(data_dir / "hermes_dlq.jsonl")
        self._callback_dispatcher = HermesCallbackDispatcher(
            sender=self._send_to_platform_strict,
            dlq_logger=self._dlq_logger,
        )

        # Webhook 服务器
        self._webhook_server = None
        self._webhook_app = None

        logger.info(
            f"[HermesBridge] 插件已初始化，Webhook URL: {self.hermes_webhook_url}"
        )

    async def initialize(self):
        """插件初始化"""
        # 启动接收 Hermes 响应的 Webhook 服务器
        await self._start_response_server()
        logger.info(f"[HermesBridge] 响应服务器已启动 on port {self.response_port}")

    async def on_message(self, event: AstrMessageEvent):
        """处理收到的 QQ 消息"""
        try:
            # 1. 提取消息信息
            message_text = ""
            for comp in event.get_messages():
                if isinstance(comp, Plain):
                    message_text += str(comp.text)

            if not message_text.strip():
                # 忽略非文本消息
                return

            # 2. 获取或创建会话映射
            user_id = str(event.get_sender_id())
            platform_id = str(event.get_platform_id())
            try:
                platform_type = PlatformType.from_astrbot_platform_id(platform_id)
            except ValueError:
                platform_type = PlatformType.QQ
            session_key = self._get_or_create_session(user_id, platform_type)

            # 缓存 session_key → unified_msg_origin，供响应回传时使用
            umo = event.unified_msg_origin
            self._umo_cache[session_key] = umo

            # 3. 构建 Webhook 数据
            message_data = {
                "user_id": user_id,
                "session_key": session_key,
                "unified_msg_origin": umo,
                "message": message_text,
                "message_type": "group" if event.is_group() else "private",
                "platform": platform_type.value,
                "message_id": str(event.message_id),
                "sender_nickname": event.get_sender_name() or user_id,
            }

            # 5. 发送 Webhook 到 Hermes
            await self._send_to_hermes(message_data)

            # 6. 标记消息已处理（可选：添加表情回复）
            # await event.send_message(MessageChain([Plain("🤔 思考中...")]))

        except Exception as e:
            logger.error(f"[HermesBridge] 处理消息失败：{e}")

    async def _send_to_hermes(self, data: dict):
        """发送消息到 Hermes Webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                # 计算 HMAC 签名
                body = json.dumps(data).encode("utf-8")
                signature = hmac.new(
                    self.hermes_secret.encode("utf-8"), body, hashlib.sha256
                ).hexdigest()

                # 发送请求
                async with session.post(
                    self.hermes_webhook_url,
                    json=data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": f"sha256={signature}",
                        "X-Webhook-Event": "qq_message",
                        "X-User-ID": data["user_id"],
                        "X-Session-Key": data["session_key"],
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(
                            f"[HermesBridge] 消息已转发 - 用户 {data['user_id']}, "
                            f"响应：{result.get('status', 'unknown')}"
                        )
                    else:
                        logger.error(
                            f"[HermesBridge] Hermes 返回错误 {response.status}: "
                            f"{await response.text()}"
                        )

        except aiohttp.ClientError as e:
            logger.error(f"[HermesBridge] 网络错误：{e}")
        except Exception as e:
            logger.error(f"[HermesBridge] 发送失败：{e}")

    async def _start_response_server(self):
        """启动接收 Hermes 响应的 Webhook 服务器"""
        try:
            from aiohttp import web

            self._webhook_app = web.Application()
            self._webhook_app.router.add_post(
                "/hermes_response", self._handle_hermes_response
            )
            self._webhook_app.router.add_post(
                "/webhooks/astrbot_qq",
                self._handle_hermes_response,  # 也处理直接 POST
            )

            runner = web.AppRunner(self._webhook_app)
            await runner.setup()

            site = web.TCPSite(runner, "0.0.0.0", self.response_port)
            await site.start()

        except ImportError:
            logger.error(
                "[HermesBridge] 缺少 aiohttp 依赖，请安装：pip install aiohttp"
            )
        except Exception as e:
            logger.error(f"[HermesBridge] 启动服务器失败：{e}")

    async def _handle_hermes_response(self, request):
        """处理 Hermes 返回的响应（G2：HMAC 校验 + 重试 + DLQ）。"""
        try:
            body = await request.read()

            # HMAC 入站校验：携带签名时必须校验通过；未携带则按 grace 模式接受
            sig_header = request.headers.get("X-Hub-Signature-256", "")
            if sig_header and not verify_hmac_signature(
                self.hermes_secret, body, sig_header
            ):
                logger.warning(
                    "[HermesBridge] X-Hub-Signature-256 校验失败，拒绝回调"
                )
                return aiohttp.web.json_response(
                    {"status": "unauthorized"}, status=401
                )

            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("[HermesBridge] 回调 body 解析失败：%s", exc)
                return aiohttp.web.json_response(
                    {"status": "bad_request"}, status=400
                )

            response_text = data.get("response", "") or data.get("message", "")
            session_key = data.get("session_key", "")
            task_id = data.get("task_id")

            if not response_text:
                logger.warning(f"[HermesBridge] 收到空响应：{data}")
                return aiohttp.web.json_response({"status": "ok"})

            # 解析 unified_msg_origin：优先从响应体取，fallback 内存缓存
            umo: str | None = data.get("unified_msg_origin") or self._umo_cache.get(
                session_key
            )
            if not umo and session_key:
                platform_user = self.session_router.get_platform_user_by_session(
                    session_key
                )
                if platform_user:
                    logger.warning(
                        "[HermesBridge] umo 缓存未命中，无法重建完整 unified_msg_origin"
                    )

            if not umo:
                logger.error(
                    f"[HermesBridge] 无法找到回传地址: session_key={session_key}"
                )
                await self._dlq_logger.log(
                    {
                        "ts": time.time(),
                        "task_id": task_id,
                        "target_umo": None,
                        "payload": {
                            "message": response_text,
                            "session_key": session_key,
                        },
                        "last_error": "umo_not_found",
                        "attempt_count": 0,
                    }
                )
                return aiohttp.web.json_response(
                    {"status": "queued_to_dlq", "reason": "umo_not_found"},
                    status=202,
                )

            outcome = await self._callback_dispatcher.send_with_retry(
                target_umo=umo,
                message=response_text,
                task_id=task_id,
                extra_payload={"session_key": session_key},
            )
            if outcome.success:
                logger.info(
                    "[HermesBridge] 已将 Hermes 响应发送回 %s (attempts=%d)",
                    umo,
                    outcome.attempts,
                )
                return aiohttp.web.json_response(
                    {"status": "ok", "umo": umo, "attempts": outcome.attempts}
                )

            logger.error(
                "[HermesBridge] 回群失败 umo=%s attempts=%d err=%s dlq=%s",
                umo,
                outcome.attempts,
                outcome.last_error,
                outcome.dlq_written,
            )
            return aiohttp.web.json_response(
                {
                    "status": "queued_to_dlq",
                    "umo": umo,
                    "attempts": outcome.attempts,
                    "last_error": outcome.last_error,
                    "dlq_written": outcome.dlq_written,
                },
                status=202,
            )

        except Exception as e:
            logger.error(f"[HermesBridge] 处理响应失败：{e}")
            return aiohttp.web.json_response(
                {"status": "error", "message": str(e)}, status=500
            )

    async def _send_to_platform_strict(self, umo: str, message: str) -> None:
        """通过 platform adapter 发送，按错误类型抛 Retriable/Permanent。"""
        message_chain = MessageChain([Plain(message)])
        try:
            success = await self.context.send_message(umo, message_chain)
        except asyncio.TimeoutError as exc:
            raise RetriableSendError(f"timeout: {exc}") from exc
        except aiohttp.ServerDisconnectedError as exc:
            raise RetriableSendError(f"server_disconnected: {exc}") from exc
        except aiohttp.ClientConnectionError as exc:
            raise RetriableSendError(f"connection: {exc}") from exc
        except aiohttp.ClientResponseError as exc:
            cls = classify_http_status(exc.status)
            if cls is RetriableSendError:
                raise RetriableSendError(f"http {exc.status}: {exc}") from exc
            raise PermanentSendError(f"http {exc.status}: {exc}") from exc
        except OSError as exc:
            raise RetriableSendError(f"os: {exc}") from exc
        if not success:
            raise PermanentSendError(
                f"context.send_message returned False for umo={umo}"
            )

    def _get_or_create_session(self, user_id: str, platform: PlatformType) -> str:
        """获取或创建持久化会话（委托给 SessionRouter）"""
        platform_user = PlatformUser(platform=platform, user_id=user_id)
        session_key = self.session_router.get_or_create_session(platform_user)
        logger.debug(
            f"[HermesBridge] session {platform.value}:{user_id} -> {session_key}"
        )
        return session_key

    async def shutdown(self):
        """插件关闭"""
        if self._webhook_server:
            await self._webhook_server.shutdown()
        logger.info("[HermesBridge] 插件已关闭")
