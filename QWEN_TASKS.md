# Qwen 可以接手的任务清单
_生成：2026-04-18_
_目的：偏分析/验证类任务，以读为主，不改核心代码。与 GPT_TASKS.md 没有重叠。_

---

## 使用说明

- 这批任务以**读、分析、产出报告/stub**为主
- 完成一个在这里打勾 `[x]`
- **与 GPT_TASKS 的分工**：GPT 管清理（archiving、.gitignore、删文件、commit），Qwen 管分析（日志、测试、配置健康、技能目录）
- **禁区（严禁修改）**：
  - `astrbot/core/harness/**`
  - `astrbot/core/core_lifecycle.py`
  - `hermes-config/SOUL.md`（可读，可以提建议，但不要直接改）
  - `hermes-config/skills/red-teaming/`（只读分析，不要修改任何脚本）
  - `SESSION_HANDOFF.md`、`GPT_TASKS.md`

---

## 🔵 Task A — 跑单元测试并报告失败

**背景：** `tests/unit/` 下有一套 harness 单元测试，最近代码动了不少（包括 memory_promoter 接入）。不知道是否还都能 pass。

**要做：**
```bash
cd /Users/dianchi/DC-Agent
python -m pytest tests/unit/ -x -q 2>&1 | tail -50
```

如果有失败，继续：
```bash
python -m pytest tests/unit/ -v --tb=short 2>&1
```

**输出：** 把结果写入 `TEST_REPORT.md`（放根目录）：

```markdown
# Unit Test Report — 2026-04-18

## 执行命令
`python -m pytest tests/unit/ -x -q`

## 结果摘要
- 总计：X passed / Y failed / Z error
- 失败测试列表：
  - `test_harness_memory.py::test_xxx` — 原因：...

## 每条失败的根因（一句话）
...

## 建议（给 Claude 看）
- 如果是因为 memory_promoter 接口变了：需要更新 test fixture
- 如果是 import error：...
```

**验收：** 产出 `TEST_REPORT.md`；不要修改任何测试文件或被测文件。

---

## 🔵 Task B — hermes-config/skills 目录健康扫描

**背景：** `hermes-config/skills/` 下有 26 个技能目录，大量是社区 skill（dreamina/github/google-workspace 等），不清楚哪些和当前架构还兼容，哪些已经过时。

**要做：** 对 26 个 skill 目录逐一：
1. 读 `SKILL.md`（如果存在）
2. 检查 `scripts/` 下的 py 文件，看 import 是否存在明显死引用（如 `from jw_claw` / 绝对路径硬编码）
3. 特别关注以下几个（重点）：
   - `autonomous-ai-agents/hermes-agent/`
   - `productivity/google-workspace/`
   - `red-teaming/godmode/`（⚠️ 只读，**不要修改**，只记录脚本 import 状态）
   - `leisure/find-nearby/`

**输出：** 写 `SKILLS_AUDIT.md`（放根目录）：

```markdown
# Skills Audit — 2026-04-18

| 技能路径 | SKILL.md 存在 | scripts 可达 | 死依赖 | 状态 | 备注 |
|---------|--------------|-------------|--------|------|------|
| autonomous-ai-agents/hermes-agent | ✅ | ✅ | 无 | 正常 | |
| red-teaming/godmode | ✅ | ⚠️ | jw_claw? | 待确认 | 只读，不修改 |
| ...

## 需要用户确认的项目
- `xxx/xxx`：脚本里 import 了 `/Users/dianchi/...` 绝对路径，跨机器会失效
```

**验收：** 产出报告；不修改任何 skill 文件；`red-teaming/` 下的脚本**绝对不动**。

---

## 🔵 Task C — 补 harness memory 集成测试 stub

**背景：** `tests/unit/test_harness_memory.py` 存在，但当前 `harness_memory.db` 从未写入过真实记录（见 SESSION_HANDOFF.md 分析）。`_build_summary` 有多个分支没有被现有测试覆盖。

**要做：**
1. 读 `astrbot/core/harness/memory_promotion.py`（已知路径）
2. 读 `tests/unit/test_harness_memory.py`
3. 找出未覆盖的 `_build_summary` 分支：
   - `result["summary"]` 非空
   - `result["workflow_validation"]["missing_outputs"]` 非空
   - `result["strategy"]` / `progress` / `decision` / `deliverables` 各字段

**输出：** 写一个 `tests/unit/test_harness_memory_extra.py` stub 文件，里面的测试函数只写函数签名 + docstring + `pass`：

```python
"""
额外的 memory promoter 覆盖测试 stub。
函数体为 pass，由 Claude 补全逻辑。
"""
import pytest
from astrbot.core.harness.memory_promotion import HarnessMemoryPromoter
# ...

async def test_promote_with_summary_field():
    """result["summary"] 非空时应创建 memory 并截断到 200 字符。"""
    pass

async def test_promote_with_missing_outputs():
    """workflow_validation.missing_outputs 非空时的提升路径。"""
    pass

# ... 覆盖所有未测试的分支
```

**验收：** stub 文件产出，`pytest tests/unit/test_harness_memory_extra.py --collect-only` 能收集到测试函数（即使全是 pass）；stub 里的 import 和参数名要和现有测试风格一致。

---

## 🔵 Task D — astrbot.log 解析报告

**背景：** 当前 `astrbot.log` 是最新一次启动的完整日志（71 行，已读）。里面有些值得关注的东西，用户忙没时间细看。

**要做：** 读 `/Users/dianchi/DC-Agent/astrbot.log`，分析：
1. 插件加载情况（哪些加载成功/失败）
2. Provider 加载情况（哪些 enabled/disabled，有几个 disabled）
3. 平台适配器（qq_official 有几个，名字是什么）
4. `routes.hall_collaboration:64` 提到 "5 agents"——这 5 个 agent 是在哪里配置的，能否从日志或配置文件里找到名单
5. 有没有 WARNING / ERROR 级别的条目

**注意：** 日志里的 ANSI 颜色码（`[32m` 等）是 terminal 格式字符，读时忽略即可。

**输出：** 写一段简洁的中文摘要，追加到 `TEST_REPORT.md` 末尾（或单独建 `STARTUP_REPORT.md`）。

---

## 🔵 Task E — channel_directory.json 结构校验

**背景：** `hermes-config/channel_directory.json` 是 Hermes 用于路由消息到对应频道的配置，格式未知，之前没有被系统性检查过。

**要做：**
1. 读 `hermes-config/channel_directory.json`
2. 读 `hermes-config/config.yaml`（了解 Hermes 对 channel 的期望格式）
3. 对照检查：每个 channel entry 是否有必填字段；有没有引用了不存在的 platform_id 或 webhook URL

**输出：** 在 `TEST_REPORT.md` 新增一个 section `## Channel Directory 健康检查` 或单建 `CHANNEL_REPORT.md`。

**如果发现问题：** 只标注 `### ⚠️ 需要修复`，不要自己改配置文件。

---

## 完成情况 — 2026-04-18

- [x] **Task D** — STARTUP_REPORT.md 已产出
- [x] **Task A** — TEST_REPORT.md 已产出（434 passed, 0 failed）
- [x] **Task C** — test_harness_memory_extra.py 已产出（10 个 test stub）
- [ ] **Task E** — 未完成
- [ ] **Task B** — 未完成

---

## 给 Qwen 的规则

- ❌ 不要改 `astrbot/core/**` 任何 `.py`
- ❌ 不要改 `hermes-config/skills/red-teaming/` 任何文件
- ❌ 不要 git commit（留给 GPT 统一处理）
- ✅ 产出文件放根目录或明确指定的 `tests/unit/` 下
- ✅ 遇到歧义，在产出文件末尾加 `### ❓ 待确认：...`
- ✅ Task A 如果 pytest 报 ImportError（比如找不到某个 astrbot 模块），把具体报错原样贴进报告，不要尝试修复 import 路径
