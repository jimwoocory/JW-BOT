# Hermes 会话系统冲突说明

## 问题背景

当前存在两个独立的会话系统与 Hermes Agent 交互：

1. **HermesUI ↔ Hermes Agent** (直接 Web 界面)
2. **AstrBot ↔ Hermes Agent** (通过 hermes_bridge 插件)

这两个系统使用**不同的会话 ID 格式和存储机制**，导致 "Session not found" 错误。

## 会话系统对比

| 特性 | HermesUI | AstrBot (hermes_bridge) |
|------|----------|------------------------|
| **会话存储** | `~/.hermes/state.db` (SQLite) | 内存 dict + JSON 文件 |
| **会话 ID 格式** | UUID (12 位 hex) | `qq_{user_id}_{uuid[:8]}` |
| **持久化** | ✅ SQLite 数据库 | ✅ JSON 文件 (已修复) |
| **会话管理** | Gateway 自动管理 | 插件手动管理 |
| **会话查找** | 在 state.db 中查找 | 在 session_mapping 中查找 |

## 冲突表现

### 场景 1：AstrBot 用户发起对话
```
QQ 用户 123456 发送消息
  ↓
hermes_bridge 创建会话：qq_123456_a1b2c3d4
  ↓
发送到 Hermes Gateway
  ↓
Gateway 在 state.db 中查找会话 qq_123456_a1b2c3d4
  ↓
❌ Session not found! (因为会话不在 state.db 中)
```

### 场景 2：HermesUI 用户发起对话
```
用户在 WebUI 点击发送
  ↓
WebUI 创建会话：abc123def456
  ↓
发送到 Hermes Gateway
  ↓
Gateway 在 state.db 中查找会话 abc123def456
  ↓
✅ 找到会话，正常对话
```

## 根本原因

**Hermes Gateway 的会话查找逻辑**（`gateway/run.py`）：
```python
def _session_key_for_source(self, source):
    # 对于 QQ 来源，期望找到 qq_{user_id}_{xxx} 格式的会话
    # 但如果会话不在 state.db 中，会返回 None
    session_key = f"qq_{user_id}"
    session = self._session_db.get_session(session_key)
    if not session:
        return "Session not found in database."
```

**问题**：hermes_bridge 创建的会话只在 `session_mapping` 中，不在 `state.db` 中。

## 解决方案

### 方案 1：持久化会话映射（已实施）✅

**改进内容**：
- ✅ 将 `session_mapping` 保存到 JSON 文件
- ✅ 插件重启后自动加载会话映射
- ✅ 避免会话 ID 丢失导致的 "Session not found"

**文件位置**：`astrbot/data/hermes_bridge_sessions.json`

**局限性**：
- ⚠️ 会话数据仍然不在 state.db 中
- ⚠️ Hermes Gateway 无法通过标准 API 查询这些会话
- ⚠️ 会话历史、标题等功能受限

### 方案 2：使用 Hermes Gateway 原生会话（推荐）🎯

**改进思路**：
让 hermes_bridge 直接使用 Hermes Gateway 的会话系统，而不是自定义会话映射。

**实现步骤**：

1. **修改 hermes_bridge 插件**，在首次对话时调用 Gateway API 创建会话：
```python
async def _create_hermes_session(self, user_id: str) -> str:
    """在 Hermes Gateway 中创建正式会话"""
    async with aiohttp.ClientSession() as session:
        # 调用 Gateway 的 /api/session/new 接口
        async with session.post(
            f"{self.hermes_webhook_url}/api/session/new",
            json={"platform": "qq", "user_id": user_id},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 200:
                data = await response.json()
                return data["session_id"]  # 返回标准 UUID 格式
            else:
                # Fallback: 使用自定义格式
                import uuid
                return f"qq_{user_id}_{uuid.uuid4().hex[:8]}"
```

2. **修改 Gateway**，支持 QQ 平台会话的创建和查找

3. **会话 ID 统一**：所有平台使用相同的 UUID 格式

**优势**：
- ✅ 会话统一存储在 state.db 中
- ✅ 支持完整的会话管理功能（标题、历史、搜索等）
- ✅ HermesUI 和 AstrBot 可以看到相同的会话列表
- ✅ 符合 Hermes 的设计架构

**缺点**：
- ⚠️ 需要修改 Hermes Gateway 代码
- ⚠️ 需要协调两个系统的会话创建逻辑

### 方案 3：会话同步机制（折中方案）

**思路**：保持两个独立的会话系统，但定期同步会话数据。

**实现**：
1. hermes_bridge 定期将会话数据写入 state.db
2. Hermes Gateway 识别 `qq_` 前缀的会话 ID
3. 双向同步会话标题、消息历史等

## 当前状态

- ✅ **方案 1 已实施**：会话映射已持久化到 JSON 文件
- ⏳ **方案 2 待实施**：需要修改 Hermes Gateway 代码
- ⏳ **方案 3 可选**：作为过渡方案

## 测试验证

### 测试步骤

1. **重启 AstrBot**：
```bash
# 重启后检查日志
tail -f /path/to/astrbot.log | grep HermesBridge
```

2. **验证会话映射加载**：
```
[HermesBridge] 成功加载 3 个会话映射
[HermesBridge] 响应服务器已启动 on port 8645
```

3. **发送 QQ 消息**：
```
[HermesBridge] 创建新会话：qq_123456 -> qq_123456_a1b2c3d4
[HermesBridge] 消息已转发 - 用户 123456, 响应：ok
```

4. **检查会话文件**：
```bash
cat astrbot/data/hermes_bridge_sessions.json
{
  "123456": "qq_123456_a1b2c3d4",
  "789012": "qq_789012_e5f6g7h8"
}
```

## 建议

### 短期（立即生效）
- ✅ 使用方案 1 的持久化修复
- ✅ 确保会话映射不会在重启后丢失
- ✅ 减少 "Session not found" 错误

### 中期（1-2 周）
- 🎯 实施方案 2：统一会话系统
- 🎯 修改 Hermes Gateway 支持 QQ 平台会话
- 🎯 实现完整的会话管理功能

### 长期（未来优化）
- 💡 实现跨平台会话同步
- 💡 支持会话迁移和合并
- 💡 提供会话历史查看功能

## 相关文件

- 插件代码：`/Users/dianchi/DC-Agent/astrbot/plugins/hermes_bridge/__init__.py`
- 会话文件：`/Users/dianchi/DC-Agent/astrbot/data/hermes_bridge_sessions.json`
- Gateway 代码：`/Users/dianchi/.hermes/hermes-agent/gateway/run.py`
- 会话数据库：`/Users/dianchi/DC-Agent/hermes-config/state.db`

## 联系与反馈

如有问题或建议，请在 JW-Bot 仓库中提交 Issue。
