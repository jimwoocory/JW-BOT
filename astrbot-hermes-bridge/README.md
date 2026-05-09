# AstrBot → Hermes Webhook 桥接方案

## 📋 架构设计

```
QQ 用户 → NapCat/OneBot → AstrBot (QQBot) → Webhook → Hermes Agent → AI 处理
                                                              ↓
QQ 用户 ← NapCat/OneBot ← AstrBot (QQBot) ← Webhook ← Hermes Agent ← 响应
```

## 🎯 实现步骤

### 步骤 1：配置 Hermes Webhook 适配器

1. **编辑 Hermes 配置文件**：
```yaml
# /Users/dianchi/DC-Agent/hermes-config/config.yaml

gateway:
  platforms:
    webhook:
      enabled: true
      host: "0.0.0.0"
      port: 8644  # Webhook 监听端口
      
      # 全局 HMAC 密钥（用于验证请求）
      secret: "your-secret-key-here"
      
      # 配置路由：接收 AstrBot 转发的消息
      routes:
        astrbot_qq:
          secret: "astrbot-secret-key"  # 路由特定密钥（覆盖全局）
          prompt: |
            QQ 用户消息：
            用户 ID: {{user_id}}
            消息内容：{{message}}
            消息类型：{{message_type}}
            
            请以助手的身份回复这条消息。
          
          # 可选：指定使用的技能
          # skills:
          #   - coding
          #   - research
          
          # 响应返回方式
          deliver: "webhook_response"
```

2. **启动 Hermes Webhook**：
```bash
cd /Users/dianchi/DC-Agent
./hermes-start.sh gateway
```

3. **验证 Webhook 已启动**：
```bash
curl http://localhost:8644/health
# 应返回：{"status": "ok"}
```

### 步骤 2：配置 AstrBot QQBot

1. **确保 QQBot 已配置**：
```yaml
# AstrBot 配置
platform:
  - id: "qq_default"
    type: "aiocqhttp"
    enable: true
    ws_reverse_host: "0.0.0.0"
    ws_reverse_port: 6199
    ws_reverse_token: ""
```

2. **安装 NapCat 或 go-cqhttp**：
   - 参考 AstrBot 文档：`/Users/dianchi/DC-Agent/docs/zh/platform/aiocqhttp.md`

### 步骤 3：创建 AstrBot 转发插件

创建一个自定义插件，将 QQ 消息转发到 Hermes Webhook：

```python
# /Users/dianchi/DC-Agent/astrbot/plugins/hermes_bridge/__init__.py

import aiohttp
import json
import hmac
import hashlib
import base64
from astrbot.api import logger
from astrbot.api.event import AstrBotEvent
from astrbot.api.star import Star, register

@register(
    "hermes_bridge",
    "hermes_bridge",
    "AstrBot 到 Hermes Agent 的 Webhook 桥接插件"
)
class HermesBridgePlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        self.hermes_webhook_url = "http://localhost:8644/webhooks/astrbot_qq"
        self.hermes_secret = "astrbot-secret-key"  # 与 Hermes 配置一致
        
    async def on_message(self, event: AstrBotEvent):
        """处理收到的 QQ 消息并转发到 Hermes"""
        
        # 1. 提取消息信息
        message_data = {
            "user_id": str(event.get_sender_id()),
            "message": event.get_message(),
            "message_type": "group" if event.is_group() else "private",
            "platform": "qq",
            "message_id": str(event.message_id),
        }
        
        # 2. 发送 Webhook 到 Hermes
        try:
            async with aiohttp.ClientSession() as session:
                # 计算 HMAC 签名
                body = json.dumps(message_data).encode('utf-8')
                signature = hmac.new(
                    self.hermes_secret.encode('utf-8'),
                    body,
                    hashlib.sha256
                ).hexdigest()
                
                # 发送请求
                async with session.post(
                    self.hermes_webhook_url,
                    json=message_data,
                    headers={
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": f"sha256={signature}",
                        "X-Webhook-Event": "qq_message"
                    }
                ) as response:
                    if response.status == 200:
                        logger.info(f"消息已转发到 Hermes: {message_data['message'][:50]}")
                    else:
                        logger.error(f"Hermes Webhook 返回错误：{response.status}")
                        
        except Exception as e:
            logger.error(f"转发消息到 Hermes 失败：{e}")
```

### 步骤 4：配置 Hermes 响应返回

Hermes 收到消息后的响应会返回给 AstrBot，需要配置 AstrBot 接收并发送回 QQ：

```python
# 在插件中添加接收响应的端点
async def start_webhook_server(self):
    """启动服务器接收 Hermes 响应"""
    from aiohttp import web
    
    app = web.Application()
    app.router.add_post('/hermes_response', self.handle_hermes_response)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', 8645)  # 使用不同端口
    await site.start()
    logger.info("Hermes 响应接收服务器已启动 on port 8645")

async def handle_hermes_response(self, request):
    """处理 Hermes 返回的响应"""
    data = await request.json()
    
    # 提取响应信息
    response_text = data.get('response', '')
    user_id = data.get('user_id')
    
    # 发送回 QQ
    try:
        await self.send_qq_message(user_id, response_text)
        logger.info(f"已将 Hermes 响应发送回 QQ 用户 {user_id}")
    except Exception as e:
        logger.error(f"发送响应到 QQ 失败：{e}")
    
    return web.Response(status=200)
```

### 步骤 5：简化方案（推荐）

如果觉得上面太复杂，可以使用更简单的方案：

#### 方案 A：使用 AstrBot 的 HTTP 请求功能

如果 AstrBot 支持 HTTP 请求插件：

1. **在 AstrBot 中配置 HTTP 请求**：
```yaml
# 当收到 QQ 消息时，自动转发到 Hermes
http_request:
  - trigger: "on_message"
    url: "http://localhost:8644/webhooks/astrbot_qq"
    method: "POST"
    headers:
      Content-Type: application/json
      X-Hub-Signature-256: "sha256={{hmac_signature}}"
    body: |
      {
        "user_id": "{{sender_id}}",
        "message": "{{message}}",
        "message_type": "{{message_type}}"
      }
```

#### 方案 B：使用 Hermes 的主动发送能力

配置 Hermes 定期轮询 AstrBot 的消息队列：

```yaml
# Hermes 配置
scheduled_tasks:
  - name: "poll_astrbot_messages"
    cron: "*/1 * * * *"  # 每分钟
    action: "http_request"
    url: "http://localhost:6185/api/messages/pending"
    method: "GET"
```

## 🔧 快速测试

### 1. 测试 Hermes Webhook

```bash
# 发送测试消息到 Hermes
curl -X POST http://localhost:8644/webhooks/astrbot_qq \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=xxx" \
  -d '{
    "user_id": "123456",
    "message": "你好，测试消息",
    "message_type": "private"
  }'
```

### 2. 查看 Hermes 日志

```bash
tail -f /Users/dianchi/DC-Agent/hermes-agent-temp/logs/gateway.log
```

### 3. 查看 AstrBot 日志

```bash
tail -f /Users/dianchi/DC-Agent/logs/astrbot.log
```

## ⚠️ 注意事项

1. **安全性**：
   - 务必配置 HMAC 密钥验证
   - 不要将密钥提交到版本控制
   - 生产环境使用 HTTPS

2. **网络配置**：
   - 确保端口未被防火墙阻止
   - 如果使用 Docker，需要映射端口

3. **性能**：
   - Webhook 请求应该异步处理
   - 考虑添加消息队列缓冲

4. **错误处理**：
   - 添加重试机制
   - 记录失败的消息

## 📊 优化建议

### 1. 添加消息队列

使用 Redis 或 RabbitMQ 缓冲消息：

```
QQ → AstrBot → Redis → Hermes → Redis → AstrBot → QQ
```

### 2. 支持流式响应

配置 Hermes 使用流式输出，实时显示 AI 响应：

```yaml
webhook:
  streaming: true
  stream_chunk_size: 50  # 字符
```

### 3. 会话管理

维护 QQ 用户和 Hermes 会话的映射：

```python
session_mapping = {
    "qq_user_123": "hermes_session_abc",
    "qq_group_456": "hermes_session_def",
}
```

---

**下一步**：选择您想要的实现方案，我可以帮您编写具体的代码！
