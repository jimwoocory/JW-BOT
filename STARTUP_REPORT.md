# Startup Report — 2026-04-18

## 执行命令
读取 `/Users/dianchi/DC-Agent/astrbot.log`（71 行）

---

## 1. 插件加载情况

所有插件加载成功，无失败：

| 插件名 | 版本 | 状态 | 备注 |
|-------|------|------|------|
| dreamina_plugin | 0.0.1 | ✅ 成功 | 即梦 AI CLI 插件，提供 3 个工具函数 |
| hermes_bridge | 1.0.0 | ✅ 成功 | Webhook URL: http://localhost:8644/webhooks/astrbot_qq |
| session_controller | v1.0.1 | ✅ 成功 | 会话控制 |
| builtin_commands | 0.0.1 | ✅ 成功 | 自带指令 |
| astrbot | 4.1.0 | ✅ 成功 | 自带插件，含人格注入等功能 |

---

## 2. Provider 加载情况

### 已启用（8 个）
| Provider | 状态 |
|---------|------|
| nvidia/nvidia/nemotron-3-super-120b-a12b | ✅ |
| nvidia/qwen/qwen3.5-122b-a10b | ✅ |
| nvidia/qwen/qwen3.5-397b-a17b | ✅ |
| ollama/gemma4:e4b | ✅ |
| minimax/MiniMax-M2.7-highspeed | ✅ |
| minimax/MiniMax-M2.7 | ✅ |
| aihubmix/gpt-5.4-nano | ✅ |
| aihubmix/glm-ocr | ✅ |

### 已禁用（2 个）
| Provider | 状态 |
|---------|------|
| aihubmix/qwen3.5-397b-a17b | ❌ disabled |
| aihubmix/gpt-5-nano | ❌ disabled |

---

## 3. 平台适配器

### 已注册的适配器
| 适配器名 | 状态 |
|---------|------|
| aiocqhttp | ✅ 已注册 |
| wecom_ai_bot | ✅ 已注册 |
| webchat | ✅ 已注册 |

### qq_official 适配器（3 个）
| 名称 | 状态 | 备注 |
|------|------|------|
| 癫池-测试 | ✅ 已加载 | WebSocket 会话已启动 |
| 癫池1号 | ✅ 已加载 | WebSocket 会话已启动 |
| 癫池-推广01 | ✅ 已加载 | WebSocket 会话已启动 |

---

## 4. "5 agents" 分析

日志第 52 行：`routes.hall_collaboration:64: Initialized agent roster with 5 agents`

### ❓ 待确认：
- 日志中**未列出** 5 个 agent 的具体名称
- 需要从 `routes.hall_collaboration` 源代码或 `hermes-config/` 下的配置文件中查找 agent 名单
- 可能位于 `hermes-config/` 下的某个 agent 配置文件或 `channel_directory.json` 中

---

## 5. WARNING / ERROR 检查

**无 WARNING 或 ERROR 级别的日志条目。** 启动过程完全正常。

---

## 6. 其他信息

| 项目 | 值 |
|------|-----|
| AstrBot 版本 | v4.22.3 |
| WebUI 状态 | 已是最新 |
| WebUI 地址 | http://localhost:6185 |
| 人格加载 | 3 个 |
| T2I 端点 | 2 个官方端点 |
| LLM 元数据 | 2268 个 LLM 已获取 |
| HermesBridge 响应服务器 | 端口 8645 |
| TempDirCleaner | 间隔 600s，清理比例 0.3 |
