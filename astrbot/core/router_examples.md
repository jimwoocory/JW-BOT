# Router 配置与使用说明

> 适用于 Hermes Router 分流层（SessionRouter）及未来的 IntentRouter。

---

## 一、SessionRouter — 会话分流层

### 1.1 核心职责

SessionRouter 负责为来自不同平台的用户创建统一的标准 session_id（UUID 格式），解决多平台会话冲突问题。

```
HermesUI ──
           ├─→ Session Router ──→ state.db (统一 UUID 会话)
AstrBot ───┘
```

### 1.2 三层会话处理机制

1. **平台用户识别**
   - 每个平台用户由 `(platform, user_id, channel_id)` 三元组唯一标识
   - 生成格式：`platform:user_id:channel_id`

2. **会话创建/复用**
   - 新用户首次发消息 → 创建新 session_id（12 位 hex UUID）
   - 老用户再次发消息 → 复用已有 session_id

3. **统一存储**
   - 所有平台会话存储到同一个 SQLite 数据库
   - 支持跨平台查询和管理

### 1.3 支持的平台

| 平台 | 标识符 | 说明 |
|------|--------|------|
| WebUI | `webui` | Hermes Web 界面 |
| QQ | `qq` | QQ 官方 API |
| Telegram | `telegram` | Telegram Bot |
| Discord | `discord` | Discord Bot |
| Slack | `slack` | Slack Bot |
| WhatsApp | `whatsapp` | WhatsApp |
| Home Assistant | `homeassistant` | 智能家居 |
| Signal | `signal` | Signal 消息 |

---

## 二、如何扩展：添加新的 workflow kind

当 GPT 完成 IntentRouter 实现后，扩展流程如下：

### 2.1 在路由配置里添加新规则

```yaml
# router_config.yaml（待 GPT 创建）
rules:
  - pattern: "/task intake marketing_plan"
    intent_type: marketing_plan
    confidence: 0.95
  - pattern: "/task intake content_delivery"
    intent_type: content_delivery
    confidence: 0.95
```

### 2.2 添加对应的测试用例

```python
@pytest.mark.asyncio
async def test_new_workflow_intent(intent_router):
    """新 workflow kind 应正确识别。"""
    message = "/task intake my_new_workflow 测试内容"
    intent = await intent_router.classify(message, {})
    assert intent.workflow_kind == "my_new_workflow"
```

### 2.3 在 Harness 中定义 workflow

无需修改 Harness 核心代码，workflow kind 在 `contracts.py` 中已定义。

---

## 三、使用示例

### 示例 1：QQ 用户创建会话

```python
from astrbot.plugins.hermes_bridge.router import (
    SessionRouter, PlatformUser, PlatformType
)

router = SessionRouter(db_path="~/.hermes/state.db")

# QQ 用户发送消息
qq_user = PlatformUser(
    platform=PlatformType.QQ,
    user_id="123456",
    channel_id="group_789"  # 可选的群组 ID
)

session_id = router.get_or_create_session(qq_user)
print(f"QQ 用户会话 ID: {session_id}")  # 输出: QQ 用户会话 ID: a1b2c3d4e5f6
```

**流程说明：**
1. Router 检查该用户是否已有会话
2. 如果没有，创建新 session_id（12 位 hex）
3. 返回 session_id 给 hermes_bridge 插件
4. hermes_bridge 用此 session_id 与 Hermes Gateway 通信

### 示例 2：多平台用户隔离

```python
# Telegram 用户
tg_user = PlatformUser(
    platform=PlatformType.TELEGRAM,
    user_id="tg_789",
    channel_id="group_abc"
)

# WebUI 用户
web_user = PlatformUser(
    platform=PlatformType.WEBUI,
    user_id="web_user_123"
)

tg_session = router.get_or_create_session(tg_user)
web_session = router.get_or_create_session(web_user)

# 不同平台用户的 session_id 完全不同
assert tg_session != web_session
```

### 示例 3：查询和删除会话

```python
# 列出所有 QQ 平台会话
qq_sessions = router.list_sessions_by_platform(PlatformType.QQ, limit=50)
for s in qq_sessions:
    print(f"  {s['session_id']} — {s['title']}")

# 通过 session_id 反查平台用户
platform_user = router.get_platform_user_by_session(tg_session)
print(f"Telegram 用户: {platform_user.user_id}")

# 删除会话
router.delete_session(tg_session)
```

### 示例 4：与 Harness 集成

```python
from astrbot.core.harness import HarnessEngine, HarnessTaskCreateRequest

# 1. 获取 session_id
session_id = router.get_or_create_session(qq_user)

# 2. 创建 Harness 任务
engine = HarnessEngine(task_store)
task = await engine.create_task(
    HarnessTaskCreateRequest(
        title="本周推广方案",
        conversation_id=f"conv-{session_id}",
        platform_id="qq",
        session_id=f"qq:123456",
        payload={"workflow_kind": "marketing_plan"},
    )
)
```

---

## 四、如何调试 Router

### 4.1 打开 debug 日志

```python
import logging
logging.getLogger('hermes_bridge.router').setLevel(logging.DEBUG)
```

这会在控制台输出：
```
[Core] [DBUG] [hermes_bridge.router:171]: Database tables initialized
[Core] [INFO] [hermes_bridge.router:204]: Created new session a1b2c3d4e5f6 for qq:123456
[Core] [DBUG] [hermes_bridge.router:198]: Found existing session a1b2c3d4e5f6 for qq:123456
```

### 4.2 单独测试一条规则

使用单元测试框架：

```bash
# 运行所有 Router 测试
uv run pytest tests/unit/test_router_intents.py -v

# 运行集成测试
uv run pytest tests/integration/test_router_harness_integration.py -v

# 运行特定测试
uv run pytest tests/unit/test_router_intents.py::test_get_or_create_session_reuse -v
```

### 4.3 检查 HTTP API 服务（独立模式）

```bash
# 启动 Router API 服务
python router.py --db ~/.hermes/state.db --api-port 8788

# 测试创建会话
curl -X POST http://localhost:8788/api/session/create \
  -H "Content-Type: application/json" \
  -d '{"platform": "qq", "user_id": "123456"}'

# 列出所有会话
curl http://localhost:8788/api/sessions

# 查看特定会话
curl http://localhost:8788/api/session/{session_id}
```

### 4.4 检查数据库内容

```bash
# 查看数据库
sqlite3 ~/.hermes/state.db ".tables"
sqlite3 ~/.hermes/state.db "SELECT * FROM session_mapping LIMIT 5;"
sqlite3 ~/.hermes/state.db "SELECT * FROM platform_users LIMIT 5;"
```

### 4.5 常见问题排查

| 问题 | 可能原因 | 排查方法 |
|------|---------|---------|
| 同一用户获得不同 session_id | platform_user_id 生成不一致 | 检查 `generate_id()` 返回值 |
| 数据库锁定 | 多进程同时写入 | 检查是否有多个 Router 实例 |
| 会话创建缓慢 | 数据库无索引 | 检查 `idx_platform_user` 等索引是否存在 |
| API 服务启动失败 | 端口被占用 | `lsof -i :8788` 检查端口 |

---

## 五、API 参考

### SessionRouter 方法

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `get_or_create_session(platform_user)` | 获取或创建会话 | PlatformUser | session_id (str) |
| `get_session_by_platform_user(platform_user)` | 查询会话 | PlatformUser | session_id or None |
| `get_platform_user_by_session(session_id)` | 反查平台用户 | session_id | PlatformUser or None |
| `list_sessions_by_platform(platform, limit)` | 列出平台会话 | PlatformType, int | List[Dict] |
| `list_all_sessions(limit)` | 列出所有会话 | int | List[Dict] |
| `set_session_title(session_id, title)` | 设置标题 | str, str | bool |
| `delete_session(session_id)` | 删除会话 | str | bool |
| `get_session_info(session_id)` | 获取会话详情 | str | SessionInfo or None |

### HTTP API（独立服务模式）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/session/create` | POST | 创建/获取会话 |
| `/api/session/{session_id}` | GET | 获取会话信息 |
| `/api/sessions` | GET | 列出所有会话 |
| `/api/sessions/{platform}` | GET | 列出平台会话 |
| `/api/session/{session_id}/title` | PUT | 设置会话标题 |
| `/api/session/{session_id}` | DELETE | 删除会话 |

---

## 六、数据模型

### PlatformUser

```python
@dataclass
class PlatformUser:
    platform: PlatformType       # 平台类型
    user_id: str                 # 平台用户 ID
    channel_id: Optional[str]    # 频道/群组 ID（可选）
    metadata: Optional[dict]     # 附加元数据（可选）
```

### SessionInfo

```python
@dataclass
class SessionInfo:
    session_id: str              # UUID 格式会话 ID
    platform_user_id: str        # 平台用户标识
    title: str                   # 会话标题
    created_at: float            # 创建时间戳
    updated_at: float            # 更新时间戳
    platform: str                # 平台名称
    platform_user_id_raw: str    # 原始用户 ID
```

### 数据库表

**platform_users** — 平台用户映射表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT (PK) | 平台用户标识 |
| platform | TEXT | 平台类型 |
| platform_user_id | TEXT | 用户 ID |
| channel_id | TEXT | 频道 ID |
| metadata | TEXT | JSON 元数据 |
| created_at | REAL | 创建时间 |

**session_mapping** — 会话映射表

| 字段 | 类型 | 说明 |
|------|------|------|
| platform_user_id | TEXT (PK) | 平台用户标识 |
| session_id | TEXT (UNIQUE) | UUID 会话 ID |
| title | TEXT | 会话标题 |
| created_at | REAL | 创建时间 |
| updated_at | REAL | 更新时间 |
