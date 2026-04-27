# Skills Audit — 2026-04-18

## 摘要

- 总计 26 个顶层 skills 目录
- 递归发现 80 个 `SKILL.md`
- 正常运行：19 个
- 有死依赖：0 个
- 需确认：7 个
- 脚本级死依赖扫描结果：
  - 未发现 `from jw_claw` / `import jw_claw`
  - 未发现 `from data.plugins.openclaw_connector import ...`
  - 未发现脚本级 `/Users/dianchi/...` 硬编码绝对路径（除 `nas` 的 SKILL.md 外）

## 详细扫描结果

| # | Skills 路径 | SKILL.md | 脚本 | 死依赖 | 状态 | 备注 |
|---|------------|---------|------|--------|------|------|
| 1 | `apple` | 4 nested | 0 files | 无 | ✅ 正常 | 含 `apple-notes`、`apple-reminders`、`findmy`、`imessage` |
| 2 | `autonomous-ai-agents` | 4 nested | 0 files | 无 | ✅ 正常 | 含 `claude-code`、`codex`、`hermes-agent`、`opencode` |
| 3 | `creative` | 9 nested | 1 file | 无 | ✅ 正常 | `excalidraw/scripts/upload.py` 无死依赖 |
| 4 | `data-science` | 1 nested | 0 files | 无 | ✅ 正常 | 仅 `jupyter-live-kernel` |
| 5 | `devops` | 1 nested | 0 files | 无 | ✅ 正常 | 仅 `webhook-subscriptions` |
| 6 | `diagramming` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有 `DESCRIPTION.md` |
| 7 | `dogfood` | 1 | 0 files | 无 | ✅ 正常 | 根目录 SKILL.md |
| 8 | `domain` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有 `DESCRIPTION.md` |
| 9 | `email` | 1 nested | 0 files | 无 | ✅ 正常 | 仅 `himalaya` |
| 10 | `feeds` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有 `DESCRIPTION.md` |
| 11 | `gaming` | 2 nested | 0 files | 无 | ✅ 正常 | `minecraft-modpack-server`、`pokemon-player` |
| 12 | `gifs` | 0 | 0 files | 无 | ⚠️ 待确认 | 仅有 `DESCRIPTION.md` |
| 13 | `github` | 6 nested | 0 files | 无 | ✅ 正常 | 覆盖 auth / issues / PR / repo / review / inspection |
| 14 | `inference-sh` | 0 | 0 files | 无 | ⚠️ 待确认 | 有产品说明，无 SKILL.md |
| 15 | `leisure` | 1 nested | 1 file | 无 | ✅ 正常 | `find_nearby.py` 使用纯标准库，无外部依赖 |
| 16 | `mcp` | 2 nested | 0 files | 无 | ✅ 正常 | `mcporter`、`native-mcp` |
| 17 | `media` | 4 nested | 1 file | 无 | ✅ 正常 | `fetch_transcript.py` 无死依赖 |
| 18 | `mlops` | 22 nested | 0 files | 无 | ✅ 正常 | 内容最多，未见旧架构依赖 |
| 19 | `nas` | 1 | 0 files | ⚠️ 绝对路径 | ⚠️ 待确认 | SKILL.md 多处硬编码 `/Users/dianchi/nas_kb` 和 `/Users/dianchi/JW-Bot/nas_sync/` |
| 20 | `note-taking` | 1 nested | 0 files | 无 | ✅ 正常 | 仅 `obsidian` |
| 21 | `productivity` | 6 nested | 12 files | 无 | ✅ 正常 | `google-workspace`、`ocr-and-documents`、`powerpoint` 等脚本均无旧依赖 |
| 22 | `red-teaming` | 1 nested | 4 files | ⚠️ 见下 | ⚠️ 待确认 | 只读分析，不修改 |
| 23 | `research` | 5 nested | 2 files | 无 | ✅ 正常 | `arxiv`、`polymarket` 无死依赖 |
| 24 | `smart-home` | 1 nested | 0 files | 无 | ✅ 正常 | 仅 `openhue` |
| 25 | `social-media` | 1 nested | 0 files | 无 | ✅ 正常 | 仅 `xitter` |
| 26 | `software-development` | 6 nested | 0 files | 无 | ✅ 正常 | 计划、调试、TDD、code review 等齐全 |

## 重点目录分析

### `autonomous-ai-agents/hermes-agent`
- ✅ SKILL.md 存在（700+ 行完整文档）
- ✅ 无脚本文件，纯文档 skill
- ✅ 状态正常，与当前架构兼容

### `productivity/google-workspace`
- ✅ SKILL.md 存在
- ✅ 3 个脚本：`google_api.py`（843 行）、`gws_bridge.py`、`setup.py`
- ✅ 使用 `HERMES_HOME` 环境变量推导路径，无硬编码
- ✅ 依赖 `google-api-python-client`、`google-auth`，需 pip 安装
- ✅ 状态正常

### `red-teaming/godmode`（⚠️ 只读，不修改）
- ✅ SKILL.md 存在
- ⚠️ 4 个脚本：`auto_jailbreak.py`、`godmode_race.py`、`load_godmode.py`、`parseltongue.py`
- 依赖：`json`、`os`、`time`、`yaml`、`pathlib`、`re`、`base64`、`concurrent.futures`
- 可选依赖：`openai`
- ✅ 无 `jw_claw` / `openclaw_connector` 旧依赖
- ✅ 无绝对路径硬编码
- ⚠️ 敏感内容，需 Claude 人工审查安全边界

### `leisure/find-nearby`
- ✅ SKILL.md 存在
- ✅ `find_nearby.py` 使用纯标准库（urllib、json、math）
- ✅ 无需 API key，使用 OpenStreetMap Overpass + Nominatim
- ✅ 状态正常

## 需要用户确认的项目

1. **`nas`**：SKILL.md 明确绑定 `/Users/dianchi/nas_kb` 与 `/Users/dianchi/JW-Bot/nas_sync/`，跨机器不可直接复用，需改为环境变量或配置注入
2. **`diagramming`、`domain`、`feeds`、`gifs`、`inference-sh`**：仅有 `DESCRIPTION.md`，无 SKILL.md，像占位目录，建议标注为 placeholder
3. **`red-teaming/godmode`**：架构兼容但内容敏感，需人工复核

## 结论

从这次扫描看，`hermes-config/skills/` 的主要问题**不是死依赖**，而是**目录语义不一致**：
- 一部分是实际可用的 skill（19 个）
- 一部分是分类容器/占位（7 个）
- 全部脚本均未发现旧架构（`jw_claw`、`openclaw_connector`）的残留依赖
