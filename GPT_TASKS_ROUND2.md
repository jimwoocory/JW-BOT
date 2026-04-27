# GPT Round 2 — 续接任务清单
_生成：2026-04-18_
_目的：接手 Qwen 额度用完留下的两个任务（B、E），完成 Task 5 commit 分拆，修复 hermes_bridge bug。_
_额度：90% 剩余，充足。_

---

## 前置条件澄清

### SESSION_HANDOFF.md 状态

**当前状况：** 我（Claude）已修改此文件，内容是 P1 待办项的核对结论（见 commit 历史）。

**处理原则：** 此文件原是"禁区"，但：
- 这是我自己的修改（记录任务状态）
- Task 5 commit 时需要明确处理它：
  - **选项 A**：把我的 SESSION_HANDOFF.md 改动**单独提一次 commit**（标注"核对 P1 结论"）
  - **选项 B**：与插件归档、.gitignore 等一起提，但 commit message 要说明包含了此文件的更新

**建议选项 A**：让 SESSION_HANDOFF.md 的改动独立，这样：
1. 清晰可追踪（谁改了什么记录）
2. 三个 commit 各司其职（归档、清理、确认）
3. 如果将来要 cherry-pick，粒度合理

---

## 🔵 Task B — Skills Audit（Qwen 未完成，接手）

**背景：** `hermes-config/skills/` 有 26 个技能目录，需要扫一遍，判断哪些和当前架构兼容。

**要做：**
1. 对 26 个 skill 目录逐一：
   ```
   ls hermes-config/skills/
   ```
   预期列表：apple, autonomous-ai-agents, creative, data-science, devops, diagramming, dogfood, domain, email, feeds, gaming, gifs, github, inference-sh, leisure, mcp, media, mlops, nas, note-taking, productivity, red-teaming, research, smart-home, social-media, software-development

2. 对每个目录：
   - 读 `SKILL.md`（如果存在）：提取 skill 名称、用途、依赖
   - 读 `scripts/` 下的 `.py` 文件，grep 是否有死依赖：
     - `from jw_claw` / `import jw_claw` 的 import
     - 硬编码绝对路径（`/Users/dianchi/...` 等）
     - `from data.plugins.openclaw_connector` 的 import
   - 特殊处理 `red-teaming/godmode/`：只读分析，**绝不修改任何内容**

3. **输出格式** — `hermes-config/skills/SKILLS_AUDIT.md`：

```markdown
# Skills Audit Report — 2026-04-18

## 摘要
- 总计 26 个 skills
- 正常运行：X 个
- 有死依赖：Y 个
- 需确认：Z 个

## 详细扫描结果

| # | Skills 路径 | SKILL.md | 脚本 | 死依赖 | 状态 | 备注 |
|---|------------|---------|------|--------|------|------|
| 1 | apple | ✅ | 2 files | 无 | ✅ 正常 | |
| 2 | autonomous-ai-agents/hermes-agent | ✅ | 3 files | 无 | ✅ 正常 | |
| ... |
| 24 | red-teaming/godmode | ✅ | 4 files | ⚠️ 见下 | ⚠️ 待确认 | 只读，不修改 |

## 发现的问题

### 有死依赖的 Skills（无法运行）

- `xxx/xxx`：依赖 `jw_claw`，已死
- `yyy/yyy`：硬编码绝对路径 `/Users/dianchi/...`

### 需要修复的 Skills（可运行但有隐患）

- `zzz/zzz`：调用已归档插件 `openclaw_core_v2`（建议改用 `hermes_bridge`）

### 仅读分析（无权修改）

- `red-teaming/godmode`：import 结构及脚本内容分析如下：
  - 主模块：godmode/SKILL.md
  - 脚本：auto_jailbreak.py、parseltongue.py、godmode_race.py、load_godmode.py
  - 依赖：references/ 下有 jailbreak-templates.md、refusal-detection.md
  - 静态 import 分析：[逐文件 import 状态]

## 建议（给 Claude 看）

1. 有死依赖的 skills 可考虑归档或删除
2. 硬编码路径的 skills 需要环境变量改造后才能跨机器
3. red-teaming/godmode 的运行正确性需要 Claude 后续手动审查（我只能读）
```

**验收：** `hermes-config/skills/SKILLS_AUDIT.md` 产出；26 个 skills 全部列在表格里；红队模块只做只读分析，不修改。

---

## 🔵 Task E — Channel Directory Validation（Qwen 未完成，接手）

**背景：** `hermes-config/channel_directory.json` 是消息路由配置，需要结构校验。

**要做：**
1. 读 `hermes-config/channel_directory.json` 的完整内容
2. 读 `hermes-config/config.yaml`（了解 Hermes 对 channel 的期望定义）
3. 校验：
   - 每个 channel entry 是否有必填字段（如 `id`, `platform_id`, `channel_name` 等——具体看结构）
   - 所有引用的 `platform_id` 是否存在
   - 所有 webhook URL 是否格式正确（http/https）
   - 有没有重复的 channel id
4. **输出格式** — `hermes-config/CHANNEL_REPORT.md`：

```markdown
# Channel Directory Validation Report — 2026-04-18

## 文件信息
- 文件路径：`hermes-config/channel_directory.json`
- 上次修改：[mtime]
- 大小：[size]

## 结构校验结果

### 必填字段检查
| channel_id | platform_id | channel_name | webhook_url | 缺失字段 | 状态 |
|------------|-------------|--------------|-------------|--------|------|
| qq_test | qq | 测试频道 | http://... | 无 | ✅ |
| ... |

### 引用完整性检查
| 问题类型 | 数量 | 具体项 |
|---------|------|--------|
| 悬空 platform_id | 0 | |
| 无效 webhook URL | 0 | |
| 重复 channel_id | 0 | |

### 总体状态
- ✅ 全部通过 / ⚠️ 有 N 个警告 / ❌ 有 N 个错误

## 发现的问题

[如果有，逐条列出；否则报告"无问题"]

## 建议

[修复建议]
```

**验收：** `hermes-config/CHANNEL_REPORT.md` 产出；没有人为改动 JSON 文件本身（只读分析）。

---

## 🔴 Task 5 续 — Git Commit 分拆（完成）

**当前状况：** 
- 插件归档：23 R（Claude）+ 12 R（GPT）= 35 R 重命名
- .gitignore + git rm --cached：多个 D（删除 tracking）和 M（.gitignore）
- 文件删除：D 两个迁移文档、astrbot.log、astrbot.err.log
- SESSION_HANDOFF.md：M（我修改的 P1 结论）
- hermes_bridge：M（GPT 发现的 bug——待修）

**拆分策略（推荐）：**

### Commit 1：Plugin & Shell Archival
```bash
git add astrbot/plugins/_archived astrbot/src/_archived
git add astrbot/plugins/
git commit -m "$(cat <<'EOF'
chore: archive dead OpenClaw plugins and jw_astrbot_shell package

Plugins archived:
- openclaw_core_v2, openclaw_briefing, openclaw_knowledge_ingest
  (depended on jw_claw which no longer exists)
- marketing_opencli, marketing_tools (same)

Package archived:
- astrbot/src/jw_astrbot_shell (no external imports, dead code)

All archived to _archived/ subdirectories to preserve git history.
Plugin loader (star_manager.py:273) automatically skips dirs without main.py.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Commit 2：Tracking & .gitignore Cleanup
```bash
git add .gitignore
git commit -m "$(cat <<'EOF'
chore: remove runtime files from git tracking and update .gitignore

Files now ignored:
- astrbot.log, astrbot.err.log
- hermes-config/state.db, state.db-wal
- hermes-config/.skills_prompt_snapshot.json, gateway_state.json
- hermes-config/sessions/, hermes-webui-state/sessions/

Local files preserved via git rm --cached.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

### Commit 3：Documentation & Config Updates
```bash
git add SESSION_HANDOFF.md README.md
git commit -m "$(cat <<'EOF'
docs: update SESSION_HANDOFF with P1 verification results

- P1 (memory_promoter): Already correctly wired, DB empty due to 
  no completed tasks with result summaries
- P2 (plugin cleanup): Complete
- Removed stale migration docs per archival

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

**要做：**
1. 依次执行上面三个 commit
2. 运行 `git log --oneline -10` 确认整洁
3. **不要** `git push`

**验收：** `git status` 干净（除了 hermes_bridge/__init__.py 待修）；提交历史清晰。

---

## 🟡 Task F — 修复 hermes_bridge @register Bug（可选但建议做）

**问题：** `astrbot/plugins/hermes_bridge/__init__.py` 的 `@register(...)` 缺 `version` 参数。

**症状：** STARTUP_REPORT 里显示加载成功，但静态检查发现会 TypeError。

**修复方案：**
1. 读 `astrbot/plugins/hermes_bridge/__init__.py`，找 `@register(...)` 行
2. 补上 `version` 参数（参考其他插件，如 `dreamina_plugin`）
3. 示例：`@register("hermes_bridge", "hermes_bridge", "描述", version="1.0.0")`
4. 运行冒烟：`python -c "from astrbot.plugins.hermes_bridge import *"`

**验收：** 冒烟通过，无 TypeError。

**Commit message：**
```bash
git add astrbot/plugins/hermes_bridge/__init__.py
git commit -m "fix: add missing version parameter to hermes_bridge @register

Fixes TypeError when plugin loader tries to instantiate hermes_bridge.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## 执行顺序

1. **Task B** (SKILLS_AUDIT) — 15-20 分钟
2. **Task E** (CHANNEL_REPORT) — 10-15 分钟
3. **Task 5** (commit 分拆) — 5 分钟
4. **Task F** (hermes_bridge fix) — 5 分钟

---

## GPT 的执行规则

- ❌ 不要改 `astrbot/core/harness/**`
- ❌ 不要改 `hermes-config/skills/red-teaming/` 任何文件（只读分析）
- ❌ 不要 `git push` / `git rebase` / 其他危险操作
- ✅ 产出 md 文件到 `hermes-config/skills/`、`hermes-config/` 或根目录
- ✅ Task F 唯一可以改源代码的地方（hermes_bridge bug 修）
- ✅ 遇到歧义在产出文件末尾加 `### ❓ 待确认：...`
