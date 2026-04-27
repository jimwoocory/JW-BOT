# Router 覆盖率分析 — 2026-04-18

## 测试统计

| 测试文件 | 通过 | 失败 | 总计 |
|---------|------|------|------|
| `tests/unit/test_router_intents.py` | 29 | 0 | 29 |
| `tests/integration/test_router_harness_integration.py` | 7 | 0 | 7 |
| 烟雾测试 (smoke_test_router.py) | 20 | 0 | 20 |
| **总计** | **56** | **0** | **56** |

## 覆盖率分析

由于 astrbot conftest.py 触发 pydantic/mcp 冲突导致 `--cov` 无法正常运行，以下覆盖率分析通过代码审查和测试对照完成。

### SessionRouter (`router.py`)

| 行范围 | 函数 | 测试覆盖 | 备注 |
|--------|------|---------|------|
| 31-53 | `PlatformType` 枚举 + `from_string` | ✅ | 5 个测试覆盖所有分支 |
| 56-87 | `PlatformUser` 数据类 | ✅ | 4 个测试覆盖 to_dict/from_dict/generate_id |
| 90-103 | `SessionInfo` 数据类 | ✅ | 通过 get_session_info 间接测试 |
| 120-171 | `SessionRouter.__init__` + `_init_database` | ✅ | 每个测试都初始化数据库 |
| 173-214 | `get_or_create_session` | ✅ | 6 个测试覆盖创建/复用/错误分支 |
| 216-247 | `_create_new_session` | ✅ | 通过 get_or_create_session 间接覆盖 |
| 249-266 | `get_session_by_platform_user` | ✅ | 2 个测试覆盖存在/不存在 |
| 267-291 | `get_platform_user_by_session` | ✅ | 2 个测试覆盖存在/不存在 |
| 293-326 | `list_sessions_by_platform` | ✅ | 2 个测试（过滤 + limit）|
| 328-357 | `list_all_sessions` | ✅ | 3 个测试覆盖空/正常/limit |
| 359-383 | `set_session_title` | ✅ | 2 个测试覆盖存在/不存在 |
| 385-415 | `delete_session` | ✅ | 2 个测试覆盖存在/不存在 + 烟雾测试 |
| 417-446 | `get_session_info` | ✅ | 2 个测试覆盖存在/不存在 |
| 452-537 | `create_router_api_server` | ❌ | HTTP API 服务器未被测试（需要 aiohttp 环境）|
| 542-560 | `main()` CLI 入口 | ❌ | CLI 入口未被测试 |

### 未覆盖的代码

1. **`create_router_api_server` (行 452-537)** — HTTP API 服务器需要 aiohttp 运行环境，建议在集成测试中单独启动。
2. **`main()` CLI 入口 (行 542-560)** — argparse CLI，建议单独测试。

### IntentRouter（GPT 待实现）

`tests/unit/test_router_intents.py` 已预留 12 个 IntentRouter 测试 stub（已注释），等待 GPT 完成 `astrbot.core.router` 模块后启用：

| 测试 | 覆盖场景 |
|------|---------|
| `test_task_new_command` | `/task new` → task_new |
| `test_task_intake_marketing_plan` | `/task intake marketing_plan` → workflow_kind |
| `test_dreamina_intent` | "生成图片" → dreamina_plugin |
| `test_github_intent` | "GitHub" → github skill |
| `test_ls_task_command` | `/task ls` → task_list |
| `test_ambiguous_message_llm_fallback` | 模糊消息 → LLM 分类 |
| `test_llm_returns_task_intent` | LLM 返回 task Intent |
| `test_llm_returns_conversation` | LLM 返回 conversation |
| `test_empty_message` | 空消息处理 |
| `test_very_long_message` | 超长消息截断 |
| `test_special_characters` | 特殊字符处理 |
| `test_multiple_intents` | 多意图取最高置信度 |

## 结论

- **SessionRouter 核心逻辑：100% 测试覆盖**（除 HTTP API 和 CLI 入口）
- **集成测试覆盖**：Router → Harness 流程正确性已验证
- **IntentRouter 测试**：stub 已就绪，等待 GPT 实现
