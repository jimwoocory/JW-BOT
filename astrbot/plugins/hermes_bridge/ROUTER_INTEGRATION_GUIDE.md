# Hermes Router 分流层集成指南

## 概述

Router 分流层解决了多平台（HermesUI、AstrBot/QQ、Telegram 等）与 Hermes Agent 对话时的会话冲突问题。

## 架构对比

### 之前（有问题）

```
HermesUI ──→ Hermes Gateway ──→ state.db (UUID 会话)
                                   ↑
AstrBot ──→ hermes_bridge ──→ 内存 dict (自定义 ID) ❌ 不一致
```

### 现在（使用 Router）

```
HermesUI ──
           ├─→ Session Router ──→ state.db (统一 UUID 会话) ✅
AstrBot ───┘                        ↑
                               所有平台统一
```

## 集成方式

### 方式 1：作为库导入（推荐用于 hermes_bridge）

**步骤 1：修改 hermes_bridge 插件**

```python
# astrbot/plugins/hermes_bridge/__init__.py

from .router import SessionRouter, PlatformUser, PlatformType

class HermesBridgePlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        
        # 初始化 Router（使用与 Hermes Gateway 相同的数据库）
        self.router = SessionRouter(db_path="~/.hermes/state.db")
        
        # 其他初始化代码...
    
    async def on_message(self, event: AstrMessageEvent):
        user_id = str(event.get_sender_id())
        channel_id = str(event.get_channel_id()) if hasattr(event, 'get_channel_id') else None
        
        # 创建平台用户对象
        platform_user = PlatformUser(
            platform=PlatformType.QQ,
            user_id=user_id,
            channel_id=channel_id,
            metadata={
                'sender_name': event.get_sender_name(),
                'message_id': str(event.message_id)
            }
        )
        
        # 获取或创建会话（返回标准 UUID）
        session_id = self.router.get_or_create_session(platform_user)
        
        # 使用 session_id 与 Hermes Gateway 通信
        message_data = {
            "user_id": user_id,
            "session_id": session_id,  # ✅ 标准 UUID 格式
            "message": message_text,
            "platform": "qq",
            # ...
        }
        
        await self._send_to_hermes(message_data)
```

**步骤 2：修改 Hermes Gateway（可选，增强功能）**

在 `gateway/run.py` 中添加 Router 支持：

```python
# gateway/run.py

from hermes_bridge.router import SessionRouter, PlatformUser, PlatformType

class HermesGateway:
    def __init__(self):
        # 初始化 Router
        self.router = SessionRouter(db_path="~/.hermes/state.db")
    
    async def handle_webhook(self, request):
        """处理平台 Webhook 请求"""
        data = await request.json()
        
        # 从请求中提取平台信息
        platform = data.get('platform', 'qq')
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        
        # 创建平台用户对象
        platform_user = PlatformUser(
            platform=PlatformType.from_string(platform),
            user_id=user_id,
            channel_id=channel_id
        )
        
        # 获取或创建会话
        session_id = self.router.get_or_create_session(platform_user)
        
        # 继续处理消息...
        await self.process_message(session_id, data)
```

### 方式 2：作为独立服务运行

**步骤 1：启动 Router API 服务**

```bash
# 后台运行 Router 服务
cd /Users/dianchi/JW-Bot/astrbot/plugins/hermes_bridge
nohup python router.py --db ~/.hermes/state.db --api-port 8788 > /tmp/router.log 2>&1 &

# 检查服务状态
curl http://localhost:8788/api/sessions
```

**步骤 2：在 hermes_bridge 中调用 API**

```python
# astrbot/plugins/hermes_bridge/__init__.py

import aiohttp

class HermesBridgePlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        self.router_api_url = "http://localhost:8788"
    
    async def get_or_create_session(self, user_id: str, channel_id: str = None):
        """调用 Router API 获取会话"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.router_api_url}/api/session/create",
                json={
                    "platform": "qq",
                    "user_id": user_id,
                    "channel_id": channel_id
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['session_id']
                else:
                    raise Exception(f"Router API error: {response.status}")
```

### 方式 3：集成到 Hermes Gateway（最彻底）

将 Router 直接集成到 Hermes Gateway 代码中：

```python
# gateway/run.py 或新建 gateway/router.py

class HermesGatewayWithRouter(HermesGateway):
    """带 Router 的 Hermes Gateway"""
    
    def __init__(self):
        super().__init__()
        self.session_router = SessionRouter(db_path="~/.hermes/state.db")
    
    async def process_message_from_platform(self, platform, user_id, channel_id, message):
        """处理来自平台的消息"""
        # 1. 通过 Router 获取会话
        platform_user = PlatformUser(
            platform=PlatformType.from_string(platform),
            user_id=user_id,
            channel_id=channel_id
        )
        session_id = self.session_router.get_or_create_session(platform_user)
        
        # 2. 使用标准会话 ID 处理消息
        await self.process_message(session_id, {
            'message': message,
            'platform': platform,
            'user_id': user_id
        })
```

## API 参考

### Router 方法

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

## 测试

### 单元测试

```python
# tests/test_router.py

import pytest
from hermes_bridge.router import SessionRouter, PlatformUser, PlatformType

@pytest.fixture
def router(tmp_path):
    db_path = tmp_path / "test.db"
    return SessionRouter(str(db_path))

def test_get_or_create_session(router):
    user = PlatformUser(
        platform=PlatformType.QQ,
        user_id="123456",
        channel_id="group_789"
    )
    
    # 第一次创建
    session_id1 = router.get_or_create_session(user)
    assert len(session_id1) == 12
    
    # 第二次获取（应该是同一个 ID）
    session_id2 = router.get_or_create_session(user)
    assert session_id1 == session_id2

def test_set_session_title(router):
    user = PlatformUser(platform=PlatformType.QQ, user_id="test")
    session_id = router.get_or_create_session(user)
    
    # 设置标题
    assert router.set_session_title(session_id, "Test Session")
    
    # 验证
    info = router.get_session_info(session_id)
    assert info.title == "Test Session"
```

### 集成测试

```bash
# 1. 启动 Router 服务
python router.py --db ~/.hermes/test_state.db --api-port 8789

# 2. 测试创建会话
curl -X POST http://localhost:8789/api/session/create \
  -H "Content-Type: application/json" \
  -d '{"platform": "qq", "user_id": "123456"}'

# 3. 测试列出会话
curl http://localhost:8789/api/sessions

# 4. 测试设置标题
curl -X PUT http://localhost:8789/api/session/{session_id}/title \
  -H "Content-Type: application/json" \
  -d '{"title": "My Test Session"}'
```

## 迁移现有会话

如果你有现有的 hermes_bridge 会话映射文件，可以迁移到 Router：

```python
# migrate_sessions.py

import json
from router import SessionRouter, PlatformUser, PlatformType

def migrate_old_sessions(mapping_file, db_path):
    """迁移旧会话映射到新 Router"""
    router = SessionRouter(db_path)
    
    # 读取旧映射
    with open(mapping_file, 'r', encoding='utf-8') as f:
        old_mapping = json.load(f)
    
    # 迁移每个会话
    for user_id, session_key in old_mapping.items():
        # 从旧格式提取信息
        # 格式：qq_{user_id}_{xxx}
        parts = session_key.split('_')
        if len(parts) >= 3 and parts[0] == 'qq':
            platform_user = PlatformUser(
                platform=PlatformType.QQ,
                user_id=parts[1],
                metadata={'legacy_session_key': session_key}
            )
            
            # 创建新会话（会生成标准 UUID）
            new_session_id = router.get_or_create_session(platform_user)
            print(f"Migrated {user_id}: {session_key} -> {new_session_id}")

if __name__ == '__main__':
    migrate_old_sessions(
        'astrbot/data/hermes_bridge_sessions.json',
        '~/.hermes/state.db'
    )
```

## 监控和日志

### 启用详细日志

```python
import logging
logging.getLogger('hermes_bridge.router').setLevel(logging.DEBUG)
```

### 监控指标

建议监控以下指标：

- 会话创建速率
- 各平台会话数量
- 数据库大小
- API 响应时间

## 故障排查

### 问题 1：会话 ID 不一致

**症状**：同一个用户获得不同的 session_id

**原因**：platform_user_id 生成逻辑不一致

**解决**：确保所有平台使用相同的 `generate_id()` 方法

### 问题 2：数据库锁定

**症状**：`sqlite3.OperationalError: database is locked`

**原因**：多个进程同时写入

**解决**：
1. 使用连接池
2. 启用 WAL 模式
3. 减少并发写入

```python
# 启用 WAL 模式
cursor.execute("PRAGMA journal_mode=WAL")
```

### 问题 3：性能问题

**症状**：会话创建缓慢

**解决**：
1. 添加索引（已默认添加）
2. 使用连接池
3. 考虑使用 PostgreSQL

## 下一步

1. ✅ 完成 Router 层实现
2. ⏳ 集成到 hermes_bridge
3. ⏳ 集成到 Hermes Gateway
4. ⏳ 添加监控和告警
5. ⏳ 编写更多测试用例

## 相关文件

- Router 实现：`router.py`
- 设计文档：`router_design.py`
- 冲突说明：`README_SESSION_CONFLICT.md`
- 测试文件：`tests/test_router.py`

## 联系

如有问题，请在 JW-Bot 仓库中提交 Issue。
