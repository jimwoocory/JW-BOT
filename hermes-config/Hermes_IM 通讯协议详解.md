# Hermes Agent IM 通讯协议详解

## 📋 概述

Hermes Agent 实现了一个**统一的消息网关架构**，支持 15+ 个即时通讯平台，所有平台适配器都遵循统一的设计模式。

## 🏗️ 架构设计

### 核心架构

```
┌─────────────────────────────────────────────────────────┐
│              Hermes Agent Core                          │
│  (Agent Loop, Memory, Skills, Tools)                   │
└─────────────────────────────────────────────────────────┘
                          │
                          │ Gateway
                          │
┌─────────────────────────────────────────────────────────┐
│           Messaging Gateway                             │
│  - Session Management                                   │
│  - Message Routing                                      │
│  - Platform Adapter Interface                           │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
   ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
   │Telegram │      │ Discord │      │WhatsApp │
   │ Adapter │      │ Adapter │      │ Adapter │
   └─────────┘      └─────────┘      └─────────┘
```

## 📱 支持的平台

### 已实现的平台适配器

| 平台 | 适配器文件 | 协议类型 | 特性 |
|------|-----------|----------|------|
| **Telegram** | `telegram.py` | HTTP Bot API | 文本/媒体/群组/论坛 |
| **Discord** | `discord.py` | WebSocket | 文本/语音/频道/线程 |
| **WhatsApp** | `whatsapp.py` | Cloud API | 文本/媒体/群组 |
| **Slack** | `slack.py` | WebSocket/HTTP | 文本/文件/频道 |
| **Signal** | `signal.py` | Signal Protocol | 端到端加密 |
| **Matrix** | `matrix.py` | Matrix Protocol | 联邦式聊天 |
| **SMS** | `sms.py` | Twilio API | 短信/彩信 |
| **Email** | `email.py` | IMAP/SMTP | 邮件收发 |
| **DingTalk** | `dingtalk.py` | HTTP API | 企业钉钉 |
| **Feishu** | `feishu.py` | HTTP API | 飞书/李可 |
| **WeCom** | `wecom.py` | HTTP API | 企业微信 |
| **Mattermost** | `mattermost.py` | WebSocket | 自托管 Slack |
| **Webhook** | `webhook.py` | HTTP POST | 通用 Webhook |
| **Home Assistant** | `homeassistant.py` | HA API | 智能家居 |
| **BlueBubbles** | `bluebubbles.py` | API | iMessage/Android |

## 🔌 平台适配器接口

### 基类：`BasePlatformAdapter`

所有平台适配器都继承自 `gateway/platforms/base.py` 中的 `BasePlatformAdapter`。

#### 核心方法

```python
class BasePlatformAdapter(ABC):
    """所有平台适配器的基类"""
    
    def __init__(self, config: PlatformConfig, platform_name: str):
        self.config = config
        self.platform_name = platform_name
        self.gateway = None  # Gateway instance
        self.session_manager = None
    
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化平台连接"""
        pass
    
    @abstractmethod
    async def start_listening(self):
        """开始监听消息"""
        pass
    
    @abstractmethod
    async def send_message(self, session_key: str, content: str) -> SendResult:
        """发送消息"""
        pass
    
    @abstractmethod
    async def stop(self):
        """停止适配器"""
        pass
```

### 消息事件模型

```python
class MessageEvent:
    """统一的消息事件模型"""
    
    def __init__(
        self,
        platform: str,           # 平台名称
        user_id: str,            # 用户 ID
        chat_id: str,            # 聊天/频道 ID
        message_id: str,         # 消息 ID
        content: str,            # 消息内容
        timestamp: datetime,     # 时间戳
        message_type: str,       # 消息类型：text/image/voice/document
        attachments: List[Attachment] = [],  # 附件
        metadata: Dict = {},     # 平台特定元数据
    ):
        self.platform = platform
        self.user_id = user_id
        self.chat_id = chat_id
        self.message_id = message_id
        self.content = content
        self.timestamp = timestamp
        self.message_type = message_type
        self.attachments = attachments
        self.metadata = metadata
```

### 会话管理

```python
class Session:
    """跨平台会话管理"""
    
    def __init__(
        self,
        session_key: str,        # 唯一会话键：platform:user_id:chat_id
        platform: str,           # 平台
        user_id: str,            # 用户 ID
        chat_id: str,            # 聊天 ID
        thread_id: Optional[str] = None,  # 线程 ID（Discord/Telegram 论坛）
    ):
        self.session_key = session_key
        self.platform = platform
        self.user_id = user_id
        self.chat_id = chat_id
        self.thread_id = thread_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.message_history = []
```

## 📡 通讯流程

### 1. 消息接收流程

```
用户消息 → 平台 API → 适配器 → Gateway → Agent Core
```

#### Telegram 示例

```python
# Telegram 适配器实现
class TelegramAdapter(BasePlatformAdapter):
    
    async def _on_message(self, update: Update, context):
        """处理收到的 Telegram 消息"""
        
        # 1. 提取消息信息
        message = update.effective_message
        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)
        content = message.text or message.caption
        
        # 2. 创建统一消息事件
        event = MessageEvent(
            platform="telegram",
            user_id=user_id,
            chat_id=chat_id,
            message_id=str(message.message_id),
            content=content,
            timestamp=message.date,
            message_type=self._detect_type(message),
            attachments=await self._extract_attachments(message),
        )
        
        # 3. 发送到 Gateway
        await self.gateway.handle_message(event)
```

### 2. 消息发送流程

```
Agent Core → Gateway → 适配器 → 平台 API → 用户
```

#### 发送消息示例

```python
async def send_message(self, session_key: str, content: str) -> SendResult:
    """发送消息到 Telegram"""
    
    # 1. 获取会话信息
    session = self.session_manager.get(session_key)
    chat_id = session.chat_id
    thread_id = session.thread_id
    
    # 2. 格式化消息（Telegram MarkdownV2）
    formatted_text = self._format_for_telegram(content)
    
    # 3. 发送消息
    message = await self._bot.send_message(
        chat_id=chat_id,
        text=formatted_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        message_thread_id=thread_id,  # 论坛话题支持
    )
    
    # 4. 返回结果
    return SendResult(
        success=True,
        message_id=str(message.message_id),
        platform="telegram",
    )
```

## 🔐 认证与安全

### 1. 平台认证方式

| 平台 | 认证方式 | 配置项 |
|------|----------|--------|
| Telegram | Bot Token | `TELEGRAM_BOT_TOKEN` |
| Discord | Bot Token | `DISCORD_BOT_TOKEN` |
| WhatsApp | API Key + Phone ID | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` |
| Slack | Bot Token | `SLACK_BOT_TOKEN` |
| Signal | Signal CLI | `SIGNAL_PHONE_NUMBER` |
| Email | IMAP/SMTP | `EMAIL_IMAP_SERVER`, `EMAIL_SMTP_SERVER` |

### 2. 用户授权

```python
# Gateway 配置中的授权控制
class GatewayConfig:
    def __init__(self):
        self.allowed_users = []  # 允许的用户 ID 列表
        self.allowed_chats = []  # 允许的聊天 ID 列表
        self.dm_only = False     # 仅允许私聊
        self.require_mention = False  # 群组中需要 @mention
        
    def is_authorized(self, event: MessageEvent) -> bool:
        """检查用户是否授权"""
        if event.user_id in self.allowed_users:
            return True
        if event.chat_id in self.allowed_chats:
            return True
        return False
```

## 🔄 会话管理

### 1. 会话键生成

```python
def generate_session_key(platform: str, user_id: str, chat_id: str) -> str:
    """生成唯一会话键"""
    return f"{platform}:{user_id}:{chat_id}"

# 示例
# telegram:123456789:123456789  (Telegram 私聊)
# discord:987654321:111222333444555666  (Discord 频道)
# whatsapp:8613800138000:8613800138000-group  (WhatsApp 群组)
```

### 2. 跨平台会话延续

Hermes 支持**跨平台会话延续**：

```python
class SessionManager:
    """会话管理器"""
    
    def link_sessions(self, primary: Session, secondary: Session):
        """链接两个会话（跨平台延续）"""
        primary.linked_sessions.append(secondary.session_key)
        secondary.linked_sessions.append(primary.session_key)
        
        # 共享消息历史
        secondary.message_history = primary.message_history.copy()
    
    def get_linked_sessions(self, session_key: str) -> List[str]:
        """获取所有关联会话"""
        session = self.sessions.get(session_key)
        return session.linked_sessions if session else []
```

### 使用场景

1. **用户在 Telegram 开始对话**
2. **切换到 Discord 继续**
3. **Hermes 自动同步上下文**

## 📊 消息格式化

### 统一格式 → 平台特定格式

```python
class MessageFormatter:
    """消息格式化器"""
    
    def format_for_platform(self, content: str, platform: str) -> str:
        """将统一格式转换为平台特定格式"""
        
        if platform == "telegram":
            return self._to_telegram_md(content)
        elif platform == "discord":
            return self._to_discord_md(content)
        elif platform == "slack":
            return self._to_slack_format(content)
        # ...
    
    def _to_telegram_md(self, content: str) -> str:
        """转换为 Telegram MarkdownV2"""
        # 转义特殊字符
        content = escape_mdv2(content)
        # 转换格式
        content = content.replace("**", "*").replace("```", "```python")
        return content
```

## 🎯 高级特性

### 1. 媒体处理

```python
class Attachment:
    """媒体附件"""
    
    def __init__(
        self,
        type: str,           # image/voice/document/video
        url: str,            # 下载 URL
        file_size: int,      # 文件大小
        mime_type: str,      # MIME 类型
        metadata: Dict = {}, # 元数据
    ):
        self.type = type
        self.url = url
        self.file_size = file_size
        self.mime_type = mime_type
        self.metadata = metadata
```

### 2. 群组控制

```python
class GroupControls:
    """群组消息控制"""
    
    def __init__(self):
        self.mention_mode = "always"  # always/mentioned/regex
        self.mention_patterns = []    # 触发关键词
        
    def should_respond(self, event: MessageEvent) -> bool:
        """判断是否应该响应"""
        if not event.is_group:
            return True  # 私聊总是响应
        
        if self.mention_mode == "always":
            return True
        elif self.mention_mode == "mentioned":
            return event.is_mentioned
        elif self.mention_mode == "regex":
            return any(pattern.search(event.content) 
                      for pattern in self.mention_patterns)
```

### 3. Webhook 模式

```python
class WebhookAdapter(BasePlatformAdapter):
    """通用 Webhook 适配器"""
    
    async def initialize(self):
        """启动 HTTP 服务器监听 Webhook"""
        from aiohttp import web
        
        self.app = web.Application()
        self.app.router.add_post(
            f"/webhook/{self.platform_name}",
            self._handle_webhook
        )
        
        runner = web.AppRunner(self.app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', self.config.webhook_port)
        await site.start()
    
    async def _handle_webhook(self, request):
        """处理 Webhook 请求"""
        payload = await request.json()
        event = self._parse_webhook_payload(payload)
        await self.gateway.handle_message(event)
        return web.Response(status=200)
```

## 🔧 配置示例

### Telegram 配置

```yaml
# config.yaml
gateway:
  platforms:
    telegram:
      enabled: true
      bot_token: "${TELEGRAM_BOT_TOKEN}"
      polling: true  # 或使用 webhook
      # webhook:
      #   url: "https://your-domain.com/webhook/telegram"
      #   port: 8443
      
      # 群组控制
      group_controls:
        mention_mode: "mentioned"  # always/mentioned/regex
      
      # 会话管理
      session:
        dm_only: false
        allowed_chats: []
```

### Discord 配置

```yaml
gateway:
  platforms:
    discord:
      enabled: true
      bot_token: "${DISCORD_BOT_TOKEN}"
      intents:
        - message_content
        - messages
        - guilds
      
      # 频道控制
      allowed_channels: []
      allow_dms: true
```

## 📈 性能优化

### 1. 消息批处理

```python
class TelegramAdapter(BasePlatformAdapter):
    """Telegram 消息批处理"""
    
    def __init__(self):
        self._text_batch_delay_seconds = 0.6  # 快速消息聚合
        self._pending_text_batches: Dict[str, MessageEvent] = {}
    
    async def _aggregate_rapid_messages(self, event: MessageEvent):
        """聚合快速连续的消息"""
        chat_key = f"{event.user_id}:{event.chat_id}"
        
        if chat_key in self._pending_text_batches:
            # 追加到现有消息
            existing = self._pending_text_batches[chat_key]
            existing.content += "\n" + event.content
            existing.timestamp = event.timestamp
        else:
            # 创建新批处理
            self._pending_text_batches[chat_key] = event
            asyncio.create_task(
                self._process_batch_after_delay(chat_key)
            )
```

### 2. 连接池

```python
class HTTPClientPool:
    """HTTP 连接池"""
    
    def __init__(self):
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
    
    def get_session(self, platform: str) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if platform not in self.sessions:
            self.sessions[platform] = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                connector=aiohttp.TCPConnector(limit=100)
            )
        return self.sessions[platform]
```

## 🔍 调试与监控

### 日志记录

```python
# Gateway 日志配置
logging_config:
  version: 1
  loggers:
    gateway:
      level: INFO
      handlers: [console, file]
    gateway.platforms.telegram:
      level: DEBUG  # 平台特定日志级别
    gateway.session:
      level: INFO
```

### 监控指标

```python
class GatewayMetrics:
    """网关监控指标"""
    
    def __init__(self):
        self.messages_received = Counter('messages_received_total', '...')
        self.messages_sent = Counter('messages_sent_total', '...')
        self.active_sessions = Gauge('active_sessions', '...')
        self.platform_errors = Counter('platform_errors_total', '...')
        self.message_latency = Histogram('message_latency_seconds', '...')
```

---

## 🔗 相关文档

- [Hermes Agent 官方文档](https://hermes-agent.nousresearch.com/docs/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Discord API](https://discord.com/developers/docs/intro)
- [WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api)

---

**文档版本**: 2026-04-11  
**Hermes Agent 版本**: v0.8.0
