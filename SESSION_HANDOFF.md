# JW-Bot Session Handoff
_生成时间：2026-04-18_

---

## 当前系统架构（实际）

```
QQ / 飞书
    ↓
AstrBot（网关 + 插件层）
    ├── OpenClaw 插件（已死，待清理）
    ├── hermes_bridge（webhook 桥接）
    └── LLM pipeline → InternalAgentSubStage
         ↓
      Harness（任务生命周期，SQLite，per-session）
         ↓
      Hermes（AI 执行后端，localhost:8787）
```

---

## 本次 session 结论汇总

### 1. AstrBot 升级（v4.22.3 → v4.23.1）
**结论：暂不升级。**

- 官方新功能（DeerFlow 2.0、Mattermost）对当前场景无用
- 高风险冲突文件：`astr_main_agent.py`（官方 +241/-68）、`builtin_commands/main.py`（官方大量删减）
- 等有实际需要的功能再做一次专门的 merge
- 如果要升级：需手动 `git merge upstream/v4.23.1`，重点解决上述两个文件的冲突

### 2. DeerFlow vs Harness
**结论：不重叠，互补。**

- DeerFlow = 外部多智能体服务（需单独跑服务器，HTTP 调用），负责 AI 执行
- Harness = 本地任务生命周期管理（SQLite，per-session），负责任务治理、记忆、review
- 理论上可以组合：Harness 创建 task → DeerFlow 执行 → Harness 完成 + 提升记忆
- 当前不需要 DeerFlow，不必引入

### 3. GPT 的六层架构图
**结论：过度设计，不要照搬。**

GPT 把调用链画成了层级，问题：
- Router 和 Harness 不是串联关系：Harness 是旁路记录器，不是中间层
- AstrBot 出现两次（网关和输出层）是同一个进程，误导
- OpenClaw 不是独立"智能层"，它是 AstrBot 的 Star 插件

**你真正需要的 Router** = OpenClaw/AstrBot 插件里的一个意图分类函数：
```
消息 → classify_intent() → 对话类 / 任务类（指定 workflow_kind）
```
已有 `HarnessWorkflowKind`：`marketing_plan`、`content_delivery`、`project_followup`、`approval_request`

### 4. Hermes 多用户适用性
**结论：作为执行后端可以继续用，但不能作为员工直接界面。**

主要问题：
- `MEMORY.md` 全局共享（所有用户共用同一个记忆文件）
- SOUL.md 单一人格，无法 per-team 配置
- 权限系统只有「配对/未配对」，无角色分级
- 无飞书原生 adapter（飞书通过 AstrBot → hermes_bridge 转发，是你自己拼的）

**当前架构下 Hermes 的问题被架空了**：
员工 → AstrBot → OpenClaw/Harness → (部分) Hermes，Hermes 只接到已处理的请求，不直接面向员工。

`hermes-config/memories/` 里的两个文件定位正确：
- `system_context.md` ✅ 全局系统知识，保留
- `development_priorities.md` ✅ 全局技术优先级，保留

不要往这里写用户/员工个人记忆。

### 5. OpenClaw → Hermes 迁移现状
**结论：OpenClaw 已经死了，直接放弃，无需迁移数据。**

- `jw_claw` 模块不存在（两个 venv 都 ImportError）
- OpenClaw 的记忆是纯内存 dict，重启即消失，**没有可迁移的持久化数据**
- AstrBot 启动时静默跳过所有 OpenClaw 插件

---

## 待办事项（按优先级）

### 🔴 优先级高（修正）

**1. ~~接通 Harness memory_promoter~~ → 实际已接通，空库是上游问题**

_2026-04-18 核对结论：_

接线已经完整（详见 [core_lifecycle.py:200-214](astrbot/core/core_lifecycle.py:200)）：
`HarnessMemoryStore` → `HarnessMemoryPromoter` → `HarnessEngine(memory_promoter=...)`。
`HarnessEngine.complete_task()` 会调用 `_maybe_promote_memory`。

`harness_memory.db` 为空的真实原因：
1. **`complete_task` 唯一调用者是 `/task complete` 命令**（`builtin_commands/commands/harness.py:359`），没人走这条路径
2. DB 里唯一那条历史任务 `f2967ef4ed3...`，`result_json` 几乎为空。即便当时走了 completed，`_build_summary()` 也会返回空字符串（[memory_promotion.py:31-50](astrbot/core/harness/memory_promotion.py:31) 要求 `summary/strategy/progress/decision/deliverables` 之一非空）
3. 大量 `tool_call_failed` 事件（OpenClaw 的 `astrbot_execute_shell` 等工具）印证了 OpenClaw 已死

**真正的下一步（如果想让记忆库活起来）：**
- 上游（`InternalAgentSubStage` / `hermes_bridge` / LLM 完成 workflow 后）需要把执行摘要写进 `result`，并主动调 `engine.complete_task(task_id, result={...})`
- 或者在 `_build_summary` 里放宽兜底（例如任务标题 + 最后一次 `assistant_response_saved` 的 preview），但这会引入低质量记忆，不建议

### 🟡 优先级中

**2. ~~清理死插件~~ → 已归档（2026-04-18）**

依赖排查结果（grep `jw_claw` / `openclaw_connector`）：

| 插件 | 依赖 `jw_claw` 或 connector | 处理 |
|------|-----------------------------|------|
| `openclaw_core_v2` | ✅ 两者都依赖 | → `_archived/` |
| `openclaw_briefing` | ✅ 两者都依赖 | → `_archived/` |
| `openclaw_knowledge_ingest` | ✅ 两者都依赖 | → `_archived/` |
| `marketing_opencli` | ✅ `jw_claw` | → `_archived/` |
| `marketing_tools` | ✅ `jw_claw` | → `_archived/` |
| `openclaw_file_ingest` | ❌ 独立（只命名带 openclaw，实际只用 astrbot.api） | 保留 |
| `opencli` | ❌ 独立（外部 node 工具包装） | 保留 |
| `minimax_token_plugin` | ❌ 独立 | 保留 |

用 `git mv` 保留历史。加载器逻辑在 [star_manager.py:273-298](astrbot/core/star/star_manager.py:273) —— 只扫顶层 `main.py`，`_archived/` 无 `main.py` 会被自动跳过，嵌套插件不会被发现。

**后续补充（2026-04-18）：**
- `astrbot/src/jw_astrbot_shell/` 已整体归档到 `astrbot/src/_archived/jw_astrbot_shell/`。复跑引用检索后未发现外部 import。
- 两份历史迁移文档 `astrbot/JW_CLAW 迁移说明.md`、`astrbot/MIGRATION_STATUS.md` 已删除，避免继续误导后续清理工作。

**3. 构建 Router（意图分类）**

在 AstrBot 插件层（或新建一个 `jw_router` Star）写意图分类函数：
- 规则匹配（关键词/命令前缀）优先
- 模糊请求走 LLM 分类（一次额外调用）
- 分类结果映射到 `HarnessWorkflowKind` 或直接对话

### 🟢 优先级低

**4. AstrBot 升级**

等官方出现对你有实际价值的功能（飞书改进、context 管理改进等）再做。
届时方式：
```bash
git remote add upstream https://github.com/AstrBotDevs/AstrBot.git
git fetch upstream
git checkout -b merge/vX.X.X
git merge upstream/vX.X.X
# 重点解决 astr_main_agent.py 的冲突
```

---

## 关键文件位置

| 文件 | 说明 |
|------|------|
| `astrbot/core/harness/engine.py` | HarnessEngine，memory_promoter 接入点 |
| `astrbot/core/harness/memory_store.py` | per-session SQLite 记忆存储 |
| `astrbot/core/harness/memory_promotion.py` | 任务完成 → 记忆提升逻辑 |
| `astrbot/core/harness/workflows.py` | HarnessWorkflowKind 定义（4 种 workflow） |
| `astrbot/core/harness/contracts.py` | HarnessTask 数据结构 |
| `data/harness.db` | 任务数据库 |
| `data/harness_memory.db` | 记忆数据库（现为空） |
| `hermes-config/memories/` | Hermes 全局系统知识（保留） |
| `astrbot/plugins/` | 插件目录（待清理 OpenClaw） |
| `data/plugins/hermes_bridge/` | Hermes webhook 桥接插件 |
