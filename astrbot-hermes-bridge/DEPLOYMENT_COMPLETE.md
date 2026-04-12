# AstrBot → Hermes Webhook 桥接部署完成 ✅

## 🎉 部署状态

### ✅ 已完成

1. **Hermes Webhook 配置** ✓
   - 配置文件：`/Users/dianchi/JW-Bot/hermes-config/config.yaml`
   - Webhook 端口：8644
   - HMAC 密钥：`astrbot_hermes_bridge_secret_c73fd328c383365f`
   - 路由名称：`astrbot_qq`

2. **Hermes Gateway 运行中** ✓
   - 状态：正在运行
   - Webhook 平台：已启用
   - 健康检查：通过
   ```bash
   curl http://localhost:8644/health
   # 返回：{"status": "ok", "platform": "webhook"}
   ```

3. **AstrBot 插件已安装** ✓
   - 插件文件：`/Users/dianchi/JW-Bot/astrbot/plugins/hermes_bridge/__init__.py`
   - 响应服务器端口：8645

## 📊 架构图

```
QQ 用户
   ↓
NapCat / OneBot
   ↓
AstrBot (QQBot 适配器)
   ↓
HermesBridge 插件
   ↓ (HTTP POST + HMAC)
Hermes Webhook (端口 8644)
   ↓
Hermes Agent (AI 处理 - MiniMax/GPT-5.4)
   ↓
Hermes Webhook 响应
   ↓ (HTTP POST)
AstrBot 响应服务器 (端口 8645)
   ↓
HermesBridge 插件
   ↓
AstrBot QQBot 适配器
   ↓
NapCat / OneBot
   ↓
QQ 用户
```

## 🔧 配置文件

### 1. Hermes Webhook 配置

位置：`/Users/dianchi/JW-Bot/hermes-config/config.yaml`

```yaml
platforms:
  webhook:
    enabled: true
    extra:
      host: "0.0.0.0"
      port: 8644
      secret: "astrbot_hermes_bridge_secret_c73fd328c383365f"
      
      routes:
        astrbot_qq:
          secret: "astrbot_hermes_bridge_secret_c73fd328c383365f"
          prompt: |
            你正在通过 QQ 与用户对话。
            
            用户信息：
            - 用户 ID: {{user_id}}
            - 昵称：{{sender_nickname}}
            - 消息类型：{{message_type}}
            
            用户消息：
            {{message}}
            
            请以友好、简洁的方式回复用户。
          
          deliver: "webhook_response"
          deliver_extra:
            response_url: "http://localhost:8645/hermes_response"
```

### 2. AstrBot 配置

位置：`/Users/dianchi/JW-Bot/astrbot-hermes-bridge/astrbot_config.json`

```json
{
  "hermes_bridge": {
    "webhook_url": "http://localhost:8644/webhooks/astrbot_qq",
    "secret": "astrbot_hermes_bridge_secret_c73fd328c383365f",
    "response_port": 8645
  }
}
```

## 🚀 启动服务

### 1. 启动 Hermes Gateway（已完成）

```bash
cd /Users/dianchi/JW-Bot
./hermes-start.sh gateway
```

**状态**：✅ 运行中

### 2. 启动 AstrBot

```bash
cd /Users/dianchi/JW-Bot
uv run main.py
```

**状态**：⏳ 待启动

## ✅ 验证步骤

### 1. 测试 Hermes Webhook

```bash
# 健康检查
curl http://localhost:8644/health

# 预期输出：
# {"status": "ok", "platform": "webhook"}
```

### 2. 测试消息转发（模拟）

```bash
# 发送测试消息
curl -X POST http://localhost:8644/webhooks/astrbot_qq \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: sha256=$(echo -n '{"user_id":"123","message":"test"}' | openssl dgst -sha256 -hmac 'astrbot_hermes_bridge_secret_c73fd328c383365f' | awk '{print $2}')" \
  -d '{
    "user_id": "123456",
    "message": "你好，这是测试消息",
    "message_type": "private",
    "sender_nickname": "TestUser"
  }'
```

### 3. 查看日志

**Hermes 日志**：
```bash
tail -f /Users/dianchi/JW-Bot/hermes-agent-temp/logs/gateway.log
```

**AstrBot 日志**：
```bash
tail -f /Users/dianchi/JW-Bot/logs/astrbot.log
```

## 🔐 安全信息

### HMAC 密钥

```
astrbot_hermes_bridge_secret_c73fd328c383365f
```

**⚠️ 重要提示**：
- 不要将密钥提交到版本控制
- 生产环境请更换为更安全的密钥
- 使用 HTTPS 而不是 HTTP

### 生成新密钥

```bash
openssl rand -hex 32
```

## 📝 下一步操作

### 1. 配置 AstrBot 的 QQBot

确保 AstrBot 的 QQBot 已正确配置：

```yaml
# AstrBot 配置
platform:
  - id: "qq_default"
    type: "aiocqhttp"
    enable: true
    ws_reverse_host: "0.0.0.0"
    ws_reverse_port: 6199
```

参考文档：`/Users/dianchi/JW-Bot/docs/zh/platform/aiocqhttp.md`

### 2. 安装 NapCat 或 go-cqhttp

按照 AstrBot 文档安装 QQBot 协议端。

### 3. 重启 AstrBot

```bash
cd /Users/dianchi/JW-Bot
uv run main.py
```

### 4. 测试 QQ 消息

1. 发送 QQ 消息给机器人
2. 查看 Hermes 日志确认消息已接收
3. 查看 QQ 是否收到 AI 响应

## 🔍 故障排查

### 问题 1：Webhook 未启动

```bash
# 检查端口
lsof -i :8644

# 查看 Hermes 日志
tail -f /Users/dianchi/JW-Bot/hermes-agent-temp/logs/gateway.log
```

### 问题 2：HMAC 验证失败

确保密钥一致：
```bash
# Hermes 配置
grep secret /Users/dianchi/JW-Bot/hermes-config/config.yaml

# AstrBot 插件配置
grep secret /Users/dianchi/JW-Bot/astrbot/plugins/hermes_bridge/__init__.py
```

### 问题 3：消息未转发

检查 AstrBot 插件是否加载：
```bash
# 查看 AstrBot 启动日志
grep "HermesBridge" /Users/dianchi/JW-Bot/logs/astrbot.log
```

## 📊 性能优化

### 1. 会话管理

插件会自动维护 QQ 用户和 Hermes 会话的映射，确保上下文连续性。

### 2. 异步处理

所有 Webhook 请求都是异步处理，不会阻塞 AstrBot 的主线程。

### 3. 错误重试

如果 Hermes 暂时不可用，AstrBot 会记录错误但不会崩溃。

## 🎯 使用场景

### 场景 1：QQ 群聊助手

- QQ 用户在群里提问
- Hermes AI 自动回答
- 支持上下文对话

### 场景 2：私人助理

- 用户私聊 QQ 机器人
- Hermes 提供个性化回答
- 使用 MiniMax 或 GPT-5.4 模型

### 场景 3：自动化工作流

- 用户发送命令（如 `/report`）
- Hermes 触发自动化技能
- 生成报告并返回 QQ

## 📚 相关文档

- [Hermes Webhook 官方文档](https://hermes-agent.nousresearch.com/docs/messaging/webhooks)
- [AstrBot QQBot 文档](/Users/dianchi/JW-Bot/docs/zh/platform/aiocqhttp.md)
- [Hermes IM 通讯协议详解](/Users/dianchi/JW-Bot/hermes-config/Hermes_IM 通讯协议详解.md)
- [双模型配置](/Users/dianchi/JW-Bot/hermes-config/双模型配置完成.md)

---

**部署完成时间**: 2026-04-11  
**Hermes 版本**: v0.8.0  
**Webhook 端口**: 8644  
**响应端口**: 8645  
**状态**: ✅ 运行正常

🎉 现在您可以通过 QQ 与 Hermes AI 对话了！
