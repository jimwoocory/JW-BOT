# AstrBot → Hermes Webhook 桥接快速启动指南

## 🎯 功能说明

通过 Webhook 将 AstrBot 收到的 QQ 消息转发给 Hermes Agent 处理，实现 QQ 用户与 Hermes AI 的对话。

## 📦 安装步骤

### 方法 1：自动配置（推荐）

```bash
cd /Users/dianchi/DC-Agent/astrbot-hermes-bridge
chmod +x setup.sh
./setup.sh
```

按照提示完成配置。

### 方法 2：手动配置

#### 1. 配置 Hermes Webhook

编辑 `hermes-config/config.yaml`，添加：

```yaml
gateway:
  platforms:
    webhook:
      enabled: true
      host: "0.0.0.0"
      port: 8644
      secret: "your-secret-key-here"  # 自定义密钥
      
      routes:
        astrbot_qq:
          secret: "your-secret-key-here"
          prompt: |
            QQ 用户消息：
            用户：{{sender_nickname}} ({{user_id}})
            内容：{{message}}
            
            请友好回复。
          deliver: "webhook_response"
          deliver_extra:
            response_url: "http://localhost:8645/hermes_response"
```

#### 2. 复制插件到 AstrBot

```bash
cp /Users/dianchi/DC-Agent/astrbot-hermes-bridge/hermes_bridge.py \
   /Users/dianchi/DC-Agent/astrbot/plugins/
```

#### 3. 配置 AstrBot

编辑 `astrbot/astrbot.json` 或在 WebUI 中添加配置：

```json
{
  "hermes_bridge": {
    "webhook_url": "http://localhost:8644/webhooks/astrbot_qq",
    "secret": "your-secret-key-here",
    "response_port": 8645
  }
}
```

## 🚀 启动服务

### 1. 启动 Hermes Gateway

```bash
cd /Users/dianchi/DC-Agent
./hermes-start.sh gateway
```

### 2. 启动 AstrBot

```bash
cd /Users/dianchi/DC-Agent
uv run main.py
```

## ✅ 验证连接

### 测试 Hermes Webhook

```bash
# 测试健康检查
curl http://localhost:8644/health

# 测试消息转发
curl -X POST http://localhost:8644/webhooks/astrbot_qq \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$(echo -n '{"user_id":"test","message":"hello"}' | openssl dgst -sha256 -hmac 'your-secret-key-here' | awk '{print $2}')" \
  -d '{
    "user_id": "test_user",
    "message": "你好，这是测试消息",
    "message_type": "private",
    "sender_nickname": "TestUser"
  }'
```

### 查看日志

**Hermes 日志**：
```bash
tail -f /Users/dianchi/DC-Agent/hermes-agent-temp/logs/gateway.log
```

**AstrBot 日志**：
```bash
tail -f /Users/dianchi/DC-Agent/logs/astrbot.log
```

## 🔧 故障排查

### 问题 1：Webhook 连接失败

```bash
# 检查端口是否监听
lsof -i :8644
lsof -i :8645

# 检查防火墙
sudo lsof -i -n | grep LISTEN
```

### 问题 2：HMAC 验证失败

确保密钥一致：
```bash
# Hermes 配置中的密钥
grep secret hermes-config/config.yaml

# AstrBot 配置中的密钥
grep secret astrbot/astrbot.json
```

### 问题 3：消息未转发

检查 AstrBot 插件是否加载：
```bash
# 查看 AstrBot 启动日志
grep "HermesBridge" logs/astrbot.log
```

## 📊 架构图

```
QQ 用户
   ↓ (QQ 消息)
NapCat / OneBot
   ↓ (OneBot 协议)
AstrBot (QQBot 适配器)
   ↓ (消息事件)
HermesBridge 插件
   ↓ (HTTP POST + HMAC)
Hermes Webhook (端口 8644)
   ↓
Hermes Agent (AI 处理)
   ↓ (AI 响应)
Hermes Webhook
   ↓ (HTTP POST)
AstrBot 响应服务器 (端口 8645)
   ↓
HermesBridge 插件
   ↓ (发送消息)
AstrBot QQBot 适配器
   ↓ (OneBot 协议)
NapCat / OneBot
   ↓
QQ 用户
```

## ⚙️ 高级配置

### 1. 自定义提示词

在 Hermes 配置中修改 `prompt`：

```yaml
routes:
  astrbot_qq:
    prompt: |
      你是一个专业的 AI 助手，正在通过 QQ 与用户交流。
      
      要求：
      1. 回答简洁明了（不超过 200 字）
      2. 语气友好亲切
      3. 使用中文回复
      4. 避免敏感话题
      
      用户 {{sender_nickname}} 说：
      {{message}}
```

### 2. 配置会话管理

启用会话保持：

```yaml
routes:
  astrbot_qq:
    session_management:
      enabled: true
      ttl: 3600  # 1 小时会话超时
      mode: "per_user"  # 每个用户独立会话
```

### 3. 添加消息过滤

只转发特定类型的消息：

```python
# 在插件中添加过滤逻辑
async def on_message(self, event: AstrBotEvent):
    # 忽略群聊消息
    if event.is_group():
        return
    
    # 只处理 @机器人的消息
    if not event.is_at_me():
        return
    
    # 转发消息到 Hermes
    await self._send_to_hermes(...)
```

### 4. 配置限流

防止滥用：

```yaml
webhook:
  rate_limit:
    enabled: true
    requests_per_minute: 10  # 每分钟最多 10 个请求
    per_user: true  # 按用户限流
```

## 🔒 安全建议

1. **使用强密钥**：
   ```bash
   # 生成随机密钥
   openssl rand -hex 32
   ```

2. **启用 HTTPS**（生产环境）：
   ```yaml
   webhook:
     ssl:
       enabled: true
       cert_file: "/path/to/cert.pem"
       key_file: "/path/to/key.pem"
   ```

3. **配置防火墙**：
   ```bash
   # 只允许本地访问
   sudo ufw allow from 127.0.0.1 to any port 8644
   sudo ufw allow from 127.0.0.1 to any port 8645
   ```

## 📈 性能优化

### 1. 异步处理

确保插件使用异步 IO：

```python
async def _send_to_hermes(self, data: dict):
    async with aiohttp.ClientSession() as session:
        # ...
```

### 2. 连接池

复用 HTTP 连接：

```python
self.session = aiohttp.ClientSession()

async def _send_to_hermes(self, data: dict):
    async with self.session.post(...) as response:
        # ...
```

### 3. 消息批处理

批量发送消息：

```python
self.message_buffer = []
self.buffer_flush_interval = 1.0  # 秒

async def flush_buffer(self):
    await asyncio.sleep(self.buffer_flush_interval)
    if self.message_buffer:
        # 批量发送
        await self._send_batch(self.message_buffer)
        self.message_buffer = []
```

## 🎉 使用示例

### 场景 1：QQ 群聊助手

1. QQ 用户在群里提问
2. AstrBot 收到消息
3. 转发到 Hermes
4. Hermes AI 回答
5. 发送回 QQ 群

### 场景 2：私人助理

1. 用户私聊 QQ 机器人
2. 消息转发到 Hermes
3. Hermes 记住会话上下文
4. 提供个性化回答

### 场景 3：自动化工作流

1. 用户发送特定命令（如 `/report`）
2. Hermes 触发自动化技能
3. 生成报告并返回 QQ

---

**有问题？** 查看日志文件或联系支持。

**文档版本**: 2026-04-11  
**适用版本**: AstrBot v4.x + Hermes Agent v0.8.0
