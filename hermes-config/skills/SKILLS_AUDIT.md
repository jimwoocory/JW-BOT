# Skills Audit Report - 2026-04-18

## 摘要

- 总计 26 个顶层 skills 目录
- 递归发现 80 个 `SKILL.md`
- 正常运行：19 个
- 有死依赖：0 个
- 需确认：7 个
- 针对脚本的死依赖扫描结果：
  - 未发现 `from jw_claw` / `import jw_claw`
  - 未发现 `from data.plugins.openclaw_connector import ...`
  - 未发现脚本级 `/Users/dianchi/...` 硬编码绝对路径

## 详细扫描结果

| # | Skills 路径 | SKILL.md | 脚本 | 死依赖 | 状态 | 备注 |
|---|------------|---------|------|--------|------|------|
| 1 | `apple` | 4 nested | 0 files | 无 | ✅ 正常 | 含 `apple-notes`、`apple-reminders`、`findmy`、`imessage`。 |
| 2 | `autonomous-ai-agents` | 4 nested | 0 files | 无 | ✅ 正常 | 含 `claude-code`、`codex`、`hermes-agent`、`opencode`。 |
| 3 | `creative` | 9 nested | 1 file | 无 | ✅ 正常 | `excalidraw/scripts/upload.py` 未发现死依赖。 |
| 4 | `data-science` | 1 nested | 0 files | 无 | ✅ 正常 | 当前仅 `jupyter-live-kernel`。 |
| 5 | `devops` | 1 nested | 0 files | 无 | ✅ 正常 | 当前仅 `webhook-subscriptions`。 |
| 6 | `diagramming` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有 `DESCRIPTION.md`，暂无可用 `SKILL.md` 实现。 |
| 7 | `dogfood` | 1 | 0 files | 无 | ✅ 正常 | 根目录直接提供 `SKILL.md`。 |
| 8 | `domain` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有内容较完整的 `DESCRIPTION.md`，但尚未落成真正 skill。 |
| 9 | `email` | 1 nested | 0 files | 无 | ✅ 正常 | 当前仅 `himalaya`。 |
| 10 | `feeds` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有 `DESCRIPTION.md`。 |
| 11 | `gaming` | 2 nested | 0 files | 无 | ✅ 正常 | `minecraft-modpack-server`、`pokemon-player`。 |
| 12 | `gifs` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有 `DESCRIPTION.md`。 |
| 13 | `github` | 6 nested | 0 files | 无 | ✅ 正常 | 覆盖 auth / issues / PR / repo / review / inspection。 |
| 14 | `inference-sh` | 0 | 0 files | 无 | ⚠️ 待确认 | 有产品说明文档，但无实际 `SKILL.md`。 |
| 15 | `leisure` | 1 nested | 1 file | 无 | ✅ 正常 | `find-nearby/scripts/find_nearby.py` 无死依赖。 |
| 16 | `mcp` | 2 nested | 0 files | 无 | ✅ 正常 | `mcporter`、`native-mcp`。 |
| 17 | `media` | 4 nested | 1 file | 无 | ✅ 正常 | `youtube-content/scripts/fetch_transcript.py` 无死依赖。 |
| 18 | `mlops` | 22 nested | 0 files | 无 | ✅ 正常 | 内容最多的目录，未见旧架构依赖。 |
| 19 | `nas` | 1 | 0 files | ⚠️ 绝对路径 | ⚠️ 待确认 | `SKILL.md` 多处硬编码 `/Users/dianchi/nas_kb` 与 `/Users/dianchi/DC-Agent/nas_sync/...`，强依赖当前机器路径。 |
| 20 | `note-taking` | 1 nested | 0 files | 无 | ✅ 正常 | 当前仅 `obsidian`。 |
| 21 | `productivity` | 6 nested | 12 files | 无 | ✅ 正常 | `google-workspace`、`ocr-and-documents`、`powerpoint` 等脚本均未见旧依赖。 |
| 22 | `red-teaming` | 1 nested | 4 files | ⚠️ 见下 | ⚠️ 待确认 | 仅做只读分析，不修改内容。 |
| 23 | `research` | 5 nested | 2 files | 无 | ✅ 正常 | `arxiv`、`polymarket` 脚本未见死依赖。 |
| 24 | `smart-home` | 1 nested | 0 files | 无 | ✅ 正常 | 当前仅 `openhue`。 |
| 25 | `social-media` | 1 nested | 0 files | 无 | ✅ 正常 | 当前仅 `xitter`。 |
| 26 | `software-development` | 6 nested | 0 files | 无 | ✅ 正常 | 计划、调试、TDD、code review 等基础技能齐全。 |

## 发现的问题

### 有死依赖的 Skills（无法运行）

- 无。按任务要求扫描的脚本级旧架构依赖模式均未命中。

### 需要修复的 Skills（可运行但有隐患）

- `nas`：`SKILL.md` 明确绑定 `/Users/dianchi/nas_kb` 与 `/Users/dianchi/DC-Agent/nas_sync/`，属于环境耦合设计，跨机器不可直接复用。
- `diagramming`：只有 `DESCRIPTION.md`，尚未形成真正可触发的 skill 目录结构。
- `domain`：描述文档存在，但缺少 `SKILL.md` 和脚本落地，当前更像待实现规格。
- `feeds`：只有 `DESCRIPTION.md`。
- `gifs`：只有 `DESCRIPTION.md`。
- `inference-sh`：只有说明文档，没有实际 `SKILL.md`。

### 仅读分析（无权修改）

- `red-teaming/godmode`：主模块为 `red-teaming/godmode/SKILL.md`，脚本共 4 个：
  - `auto_jailbreak.py`
  - `godmode_race.py`
  - `load_godmode.py`
  - `parseltongue.py`
- 依赖与结构：
  - `auto_jailbreak.py`：依赖 `json`、`os`、`time`、`yaml`、`pathlib`，可选依赖 `openai`
  - `godmode_race.py`：依赖 `os`、`re`、`time`、`concurrent.futures`，可选依赖 `openai`
  - `load_godmode.py`：依赖 `os`、`sys`、`pathlib`
  - `parseltongue.py`：依赖 `re`、`base64`
- 静态 import 分析：
  - 未发现 `jw_claw` / `openclaw_connector` 旧依赖
  - 未发现 `/Users/dianchi/...` 绝对路径
  - 代码通过 `HERMES_HOME` 和 `Path.home()` 推导默认位置，偏向 Hermes 当前架构
- 风险判断：
  - 该目录本身是高风险红队内容，虽然从“架构兼容性”看没有旧依赖，但其运行正确性和安全边界应由 Claude 后续人工审查

## 建议（给 Claude 看）

1. `nas` 应优先改成环境变量或配置注入，而不是把本机绝对路径写进 `SKILL.md`。
2. `diagramming`、`domain`、`feeds`、`gifs`、`inference-sh` 目前更像分类/占位目录；如果近期不会实现，建议标注为 placeholder，避免被误判为可用 skill。
3. `red-teaming/godmode` 从静态结构看不依赖旧 OpenClaw/JW-claw 代码，但由于内容敏感且带自动化脚本，仍应保持只读并做人工复核。
4. 从这次扫描看，`hermes-config/skills/` 的主要问题不是“死依赖”，而是“目录语义不一致”：一部分是实际 skill，一部分是分类容器，一部分是说明占位。
