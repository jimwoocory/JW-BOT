# Router 烟雾测试与边界检验报告 — 2026-04-18

## 场景 1：平台用户标识生成

| 输入 | 期望 | 实际 | ✓/✗ | 备注 |
|------|------|------|-----|------|
| `qq:user1` | Valid session_id | sid=508bdd64e2ef | ✅ | generate_id=qq:user1 |
| `qq:user1:group1` | Valid session_id | sid=8be82d94d60b | ✅ | generate_id=qq:user1:group1 |
| `telegram:user2` | Valid session_id | sid=cf64b88b0288 | ✅ | generate_id=telegram:user2 |

## 场景 2：多种平台类型

| 平台 | 期望 | 实际 | ✓/✗ | 备注 |
|------|------|------|-----|------|
| webui | 12-char session_id | 0fc4abe281c5 | ✅ | |
| qq | 12-char session_id | b66f428a12e5 | ✅ | |
| telegram | 12-char session_id | 599cdb43559b | ✅ | |
| discord | 12-char session_id | 63bf658a3941 | ✅ | |
| slack | 12-char session_id | 26401928741f | ✅ | |
| whatsapp | 12-char session_id | 55e0e6781f66 | ✅ | |
| homeassistant | 12-char session_id | fce4bcd8f1c9 | ✅ | |
| signal | 12-char session_id | dbb212d375c8 | ✅ | |

## 场景 3：边界情况

| 输入 | 期望 | 实际 | ✓/✗ | 备注 |
|------|------|------|-----|------|
| 空 user_id | 12-char session_id | c7bd87725c54 | ✅ | 空 user_id 仍可创建会话 |
| 超长 user_id (500 chars) | 12-char session_id | 0318e6e3dbe5 | ✅ | 超长 user_id 仍可处理 |
| 特殊字符 user_id | 12-char session_id | 4b630405a921 | ✅ | 含 `!@#$%^&*()_+=[]{}|;:',.<>?/~`` 等特殊字符 |
| 中文 user_id | 12-char session_id | 2e862f86ae49 | ✅ | 中文字符仍可处理 |
| 重复获取同一用户 | same session_id | 2fa290547566 == 2fa290547566 | ✅ | 幂等性正确 |
| 删除后重建 | different session_id | 7ea28db0216a != 206e335d1c54 | ✅ | 删除后创建新 ID |

## 场景 4：列表与查询

| 输入 | 期望 | 实际 | ✓/✗ | 备注 |
|------|------|------|-----|------|
| 20 QQ users, limit=10 | 10 results | 10 | ✅ | limit 参数生效 |
| nonexistent session_id | None | None | ✅ | 不存在的 session_id 正确返回 None |
| 设置标题后查询 | 测试标题 | 测试标题 | ✅ | 标题更新生效 |

## 汇总

**20/20 通过, 0 失败**

## 发现的问题

**无发现严重问题。** SessionRouter 核心逻辑稳定可靠。

### 轻微观察

1. **空 user_id 可创建会话**：`PlatformUser(platform=QQ, user_id="")` 仍能成功创建 session_id（生成 `qq:` 标识）。虽然不会崩溃，但建议在实际应用层增加 user_id 非空校验。

2. **超长 user_id 未截断**：500 字符 user_id 直接存入 SQLite 的 TEXT 字段。SQLite 能处理，但数据库体积可能膨胀。建议应用层限制 user_id 长度（如 256 字符）。

3. **删除后重新创建**：删除 session 后立即为同一用户创建，会生成新的 session_id。这是正确行为，但如果有外部系统缓存了旧 session_id，可能需要考虑 TTL 或通知机制。

## 建议（给 Claude/GPT 看）

1. **IntentRouter 实现时**：建议参考 SessionRouter 的测试模式，使用临时数据库 + pytest fixture 隔离测试数据。

2. **集成 hermes_bridge 时**：建议在插件入口增加 user_id 非空校验，避免空 user_id 产生脏数据。

3. **channel_directory.json 问题**（来自之前的 Task E）：当前 `channel_directory.json` 中完全没有 `webhook` 平台配置，但 `config.yaml` 中已启用 webhook（端口 8644，含 `astrbot_qq` 路由）。Hermes 可能无法正确路由来自 AstrBot 的 QQ 消息。建议补充：
   ```json
   {
     "platforms": {
       "webhook": [
         {
           "id": "astrbot_qq",
           "webhook_url": "http://localhost:8644/webhooks/astrbot_qq"
         }
       ]
     }
   }
   ```
