"""
AstrBot 到 Hermes Agent 的 Webhook 桥接插件

功能：
1. 将 QQ 消息转发到 Hermes Webhook
2. 接收 Hermes 响应并发送回 QQ
3. 维护会话映射

配置：
在 astrbot.json 中添加：
{
  "hermes_bridge": {
    "webhook_url": "http://localhost:8644/webhooks/astrbot_qq",
    "secret": "astrbot-secret-key",
    "response_port": 8645
  }
}
"""

import aiohttp
import json
import hmac
import hashlib
import asyncio
from typing import Optional
from astrbot.api import logger
from astrbot.api.event import AstrBotEvent, MessageChain
from astrbot.api.message_components import Plain
from astrbot.api.star import Star, register
from astrbot.api.platform import AstrBotMessage


@register(
    "hermes_bridge",
    "hermes_bridge",
    "AstrBot 到 Hermes Agent 的 Webhook 桥接"
)
class HermesBridgePlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        
        # 从配置加载
        config = context.get_config()
        self.hermes_webhook_url = config.get("hermes_bridge", {}).get(
            "webhook_url", 
            "http://localhost:8644/webhooks/astrbot_qq"
        )
        self.hermes_secret = config.get("hermes_bridge", {}).get(
            "secret", 
            "astrbot-secret-key"
        )
        self.response_port = config.get("hermes_bridge", {}).get(
            "response_port", 
            8645
        )
        
        # 会话映射：qq_user_id -> hermes_session_key
        self.session_mapping = {}
        
        # Webhook 服务器
        self._webhook_server = None
        self._webhook_app = None
        
        logger.info(f"[HermesBridge] 插件已初始化，Webhook URL: {self.hermes_webhook_url}")
    
    async def initialize(self):
        """插件初始化"""
        # 启动接收 Hermes 响应的 Webhook 服务器
        await self._start_response_server()
        logger.info(f"[HermesBridge] 响应服务器已启动 on port {self.response_port}")
    
    async def on_message(self, event: AstrBotEvent):
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
            session_key = self._get_or_create_session(user_id)
            
            # 3. 构建 Webhook 数据
            message_data = {
                "user_id": user_id,
                "session_key": session_key,
                "message": message_text,
                "message_type": "group" if event.is_group() else "private",
                "platform": "qq",
                "message_id": str(event.message_id),
                "sender_nickname": event.get_sender_name() or user_id,
            }
            
            # 4. 发送 Webhook 到 Hermes
            await self._send_to_hermes(message_data)
            
            # 5. 标记消息已处理（可选：添加表情回复）
            # await event.send_message(MessageChain([Plain("🤔 思考中...")]))
            
        except Exception as e:
            logger.error(f"[HermesBridge] 处理消息失败：{e}")
    
    async def _send_to_hermes(self, data: dict):
        """发送消息到 Hermes Webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                # 计算 HMAC 签名
                body = json.dumps(data).encode('utf-8')
                signature = hmac.new(
                    self.hermes_secret.encode('utf-8'),
                    body,
                    hashlib.sha256
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
                        "X-Session-Key": data["session_key"]
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
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
                '/hermes_response',
                self._handle_hermes_response
            )
            self._webhook_app.router.add_post(
                '/webhooks/astrbot_qq',
                self._handle_hermes_response  # 也处理直接 POST
            )
            
            runner = web.AppRunner(self._webhook_app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', self.response_port)
            await site.start()
            
        except ImportError:
            logger.error("[HermesBridge] 缺少 aiohttp 依赖，请安装：pip install aiohttp")
        except Exception as e:
            logger.error(f"[HermesBridge] 启动服务器失败：{e}")
    
    async def _handle_hermes_response(self, request):
        """处理 Hermes 返回的响应"""
        try:
            data = await request.json()
            
            # 提取响应信息
            response_text = data.get('response', '') or data.get('message', '')
            session_key = data.get('session_key', '')
            user_id = data.get('user_id', '')
            
            if not response_text:
                logger.warning(f"[HermesBridge] 收到空响应：{data}")
                return aiohttp.web.Response(status=200)
            
            # 查找对应的 QQ 用户
            if not user_id and session_key:
                # 从会话映射反查用户 ID
                user_id = self.session_mapping.get(session_key)
            
            if not user_id:
                logger.error(f"[HermesBridge] 找不到用户 ID: session_key={session_key}")
                return aiohttp.web.Response(status=404)
            
            # 发送回 QQ
            await self._send_to_qq(user_id, response_text)
            
            logger.info(f"[HermesBridge] 已将 Hermes 响应发送回 QQ 用户 {user_id}")
            
            return aiohttp.web.Response(
                status=200,
                text=json.dumps({"status": "ok", "user_id": user_id})
            )
            
        except Exception as e:
            logger.error(f"[HermesBridge] 处理响应失败：{e}")
            return aiohttp.web.Response(status=500, text=str(e))
    
    async def _send_to_qq(self, user_id: str, message: str):
        """发送消息到 QQ"""
        try:
            # 获取平台实例
            platform = self.context.get_platform()
            
            # 构造消息链
            message_chain = MessageChain([Plain(message)])
            
            # 发送消息（这里需要根据实际 API 调整）
            # 注意：AstrBot 的 API 可能需要不同的调用方式
            logger.debug(f"[HermesBridge] 准备发送消息到 QQ {user_id}: {message[:50]}...")
            
            # TODO: 这里需要根据 AstrBot 的实际 API 调整
            # 可能需要使用 event.send_message() 或其他方式
            
        except Exception as e:
            logger.error(f"[HermesBridge] 发送消息到 QQ 失败：{e}")
    
    def _get_or_create_session(self, user_id: str) -> str:
        """获取或创建会话"""
        if user_id not in self.session_mapping:
            # 创建新会话
            import uuid
            session_key = f"qq_{user_id}_{uuid.uuid4().hex[:8]}"
            self.session_mapping[user_id] = session_key
            logger.info(f"[HermesBridge] 创建新会话：{user_id} -> {session_key}")
        
        return self.session_mapping[user_id]
    
    async def shutdown(self):
        """插件关闭"""
        if self._webhook_server:
            await self._webhook_server.shutdown()
        logger.info("[HermesBridge] 插件已关闭")
