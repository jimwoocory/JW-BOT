"""
[已归档 - v1.0.0，不再加载]
活跃版本为 data/plugins/hermes_bridge/hermes_bridge.py (v2.0.0)

AstrBot 到 Hermes Agent 的 Webhook 桥接插件（旧版）

旧版消息流：AstrBot 收消息 → SessionRouter → 转发到 Hermes
新版消息流：AstrBot LLM 先处理 → 不满意时 → IntentRouter 升级到 Hermes
"""

import hashlib
import hmac
import json
from pathlib import Path

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Plain
from astrbot.api.star import Star

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

        # 持久化会话路由（SQLite）
        db_path = (
            Path(context.get_config_path()).parent.parent
            / "data"
            / "hermes_sessions.db"
        )
        self.session_router = SessionRouter(str(db_path))

        # session_key → unified_msg_origin 的内存缓存（重启后由首条消息重建）
        self._umo_cache: dict[str, str] = {}

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
        """处理 Hermes 返回的响应"""
        try:
            data = await request.json()

            response_text = data.get("response", "") or data.get("message", "")
            session_key = data.get("session_key", "")

            if not response_text:
                logger.warning(f"[HermesBridge] 收到空响应：{data}")
                return aiohttp.web.Response(status=200)

            # 解析 unified_msg_origin：优先从响应体取，fallback 内存缓存
            umo: str | None = data.get("unified_msg_origin") or self._umo_cache.get(
                session_key
            )
            if not umo and session_key:
                # 最终 fallback：从 SessionRouter 反查，只拿到平台+user_id
                platform_user = self.session_router.get_platform_user_by_session(
                    session_key
                )
                if platform_user:
                    logger.warning(
                        "[HermesBridge] umo 缓存未命中，无法重建完整 unified_msg_origin，"
                        "响应将丢失（请重启后重发一条消息以刷新缓存）"
                    )

            if not umo:
                logger.error(
                    f"[HermesBridge] 无法找到回传地址: session_key={session_key}"
                )
                return aiohttp.web.Response(status=404)

            await self._send_to_platform(umo, response_text)

            logger.info(f"[HermesBridge] 已将 Hermes 响应发送回 {umo}")
            return aiohttp.web.Response(
                status=200,
                text=json.dumps({"status": "ok", "umo": umo}),
            )

        except Exception as e:
            logger.error(f"[HermesBridge] 处理响应失败：{e}")
            return aiohttp.web.Response(status=500, text=str(e))

    async def _send_to_platform(self, umo: str, message: str):
        """通过 unified_msg_origin 将消息发回原平台用户"""
        try:
            message_chain = MessageChain([Plain(message)])
            success = await self.context.send_message(umo, message_chain)
            if not success:
                logger.error(
                    f"[HermesBridge] context.send_message 返回 False，umo={umo}"
                )
        except Exception as e:
            logger.error(f"[HermesBridge] 发送消息失败 umo={umo}：{e}")

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
