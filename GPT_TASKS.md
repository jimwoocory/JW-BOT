# GPT 可以接手的任务清单
_生成：2026-04-18_
_目的：把机械、可独立完成的任务交给 GPT-5.4，不阻塞 Claude 这边的 P3 Router / 架构类工作。_

---

## 使用说明

- 每个任务自包含：直接交给 GPT 就行，不需要看 SESSION_HANDOFF.md 也能做
- 完成一个在这里打勾 `[x]`
- 所有改动集中在明确的文件/目录内，不会碰到 Claude 正在做的架构文件
- **禁区**（Claude 在动的，GPT 不要碰）：
  - `astrbot/core/harness/**`
  - `astrbot/core/core_lifecycle.py`
  - `SESSION_HANDOFF.md`（除非专门让 GPT 更新）
  - 任何新建的 `jw_router` / Router 相关代码

---

## [x] Task 1 — 验证并归档 `astrbot/src/jw_astrbot_shell/`

**背景：** Claude 已 grep 全仓，确认 `jw_astrbot_shell` 这个包**无任何 import**，是死代码。里面还镜像着一套已经淘汰的 OpenClaw 插件副本。

**要做：**
1. 再做一次最终验证（防止 grep 漏）：
   ```bash
   grep -rn "jw_astrbot_shell\|from .*jw_astrbot_shell\|import jw_astrbot_shell" /Users/dianchi/DC-Agent \
     --include="*.py" --include="*.toml" --include="*.cfg" --include="*.json" --include="*.yaml" \
     2>/dev/null | grep -v __pycache__ | grep -v "/src/jw_astrbot_shell/" | grep -v "/.claude/"
   ```
2. 如果确实为空：
   ```bash
   mkdir -p astrbot/src/_archived
   git mv astrbot/src/jw_astrbot_shell astrbot/src/_archived/jw_astrbot_shell
   ```
3. 重跑 1 次 `astrbot` 启动冒烟（或者至少 `python -c "import astrbot"`）确认无 ImportError

**验收：** `git status` 看到 `R` 重命名条目；启动不报错。

结果：复跑全仓 grep 未发现外部引用；已 `git mv` 到 `astrbot/src/_archived/jw_astrbot_shell`；并用 `UV_CACHE_DIR=/tmp/uv-cache PYTHONPATH=/Users/dianchi/DC-Agent uv run python -c "import astrbot"` 冒烟通过。

---

## [x] Task 2 — 整理 `.gitignore` 里的日志/状态文件

**背景：** `git status` 里一堆不该被追踪的东西正在污染 diff：

```
 M astrbot.err.log
 M astrbot.log
 M hermes-config/state.db
 M hermes-config/state.db-wal
 M hermes-config/.skills_prompt_snapshot.json
 M hermes-config/sessions/session_*.json
 M hermes-config/gateway_state.json
 D hermes-webui-state/sessions/...
```

**要做：**
1. 读当前的 `.gitignore`
2. 把以下模式加进去（如果还没的话）：
   ```
   astrbot.log
   astrbot.err.log
   *.log
   hermes-config/state.db
   hermes-config/state.db-wal
   hermes-config/state.db-shm
   hermes-config/.skills_prompt_snapshot.json
   hermes-config/gateway_state.json
   hermes-config/sessions/
   hermes-webui-state/sessions/
   ```
3. 对已经被追踪的文件执行 `git rm --cached <path>` 让它们脱离追踪（但不删本地文件）
4. **不要** `git add .`，只 add `.gitignore` 和明确的 rm --cached 结果

**验收：** `git status` 变干净很多；这些文件未来改动不会再出现在 diff 里；本地文件仍然存在。

**注意：** `auth.json`、`config.yaml` 这类配置文件不要动，是用户主动管理的。

结果：已补充 `.gitignore` 规则，并对 `astrbot*.log`、`hermes-config/state.db*`、`hermes-config/.skills_prompt_snapshot.json`、`hermes-config/gateway_state.json`、`hermes-config/sessions/`、`hermes-webui-state/sessions/` 执行 `git rm --cached`，本地文件保留。

---

## [x] Task 3 — 删掉过期的 migration 文档

**背景：** OpenClaw 已经死，相关 migration 文档是陈年文件，留着造成困惑。

**文件：**
- `astrbot/JW_CLAW 迁移说明.md`
- `astrbot/MIGRATION_STATUS.md`
- `harness-engineering-phase1-plan.md`（根目录的，看是否还有引用价值）

**要做：**
1. 读每个文件，判断是不是纯历史记录
2. 如果确实已经没有当前价值：`git rm` 删掉
3. 如果还有一小段当前仍适用的内容，摘出来加到 `SESSION_HANDOFF.md` 末尾的「历史参考」section，再删原文件

**验收：** 这些 md 从仓库消失或被整合；`grep -r "JW_CLAW 迁移说明" .` 找不到任何引用链接。

结果：已删除 `astrbot/JW_CLAW 迁移说明.md` 和 `astrbot/MIGRATION_STATUS.md`；`harness-engineering-phase1-plan.md` 仍被 `hermes-config/memories/` 明确引用，因此保留。

### 需要用户确认：`SESSION_HANDOFF.md` 里仍有一处对 `JW_CLAW 迁移说明.md` 的历史引用。按“不要碰禁区”的要求，这一处我没有改；如果要严格满足 grep 验收，需要允许同步更新该文件。

---

## [x] Task 4 — 健康检查剩下的活插件

**背景：** 归档后，`astrbot/plugins/` 还剩这些：`dreamina_plugin`、`hermes_bridge`、`minimax_token_plugin`、`openclaw_file_ingest`、`opencli`。验证它们**真的能加载**，不要有隐性死代码。

**要做：** 对每个插件：
1. 打开 `main.py`，读 import 段
2. 对每个 `from X import Y`，验证 X 存在且能 import
3. 对 `@star.register(...)` 的 metadata 做个一览表

**输出：** 写一个 `PLUGIN_HEALTH.md`（放 `astrbot/plugins/` 下）：

```markdown
# Plugin Health Report — 2026-04-18

| 插件 | 状态 | import 全部可达 | 注册名 | 备注 |
|------|------|----------------|--------|------|
| dreamina_plugin | ✅ | yes | ... | ... |
| ...
```

**验收：** 报告文件产出；若发现坏插件，在表格里标红 + 附上修复建议（不要自动归档，让用户决定）。

结果：已产出 `astrbot/plugins/PLUGIN_HEALTH.md`。发现 `hermes_bridge` 存在真实加载问题：`@register(...)` 缺少 `version` 参数，模块导入时报 `TypeError`；其余活插件静态 import 可达，模块导入冒烟通过。

---

## 🟢 Task 5 — 分两次 commit 现有改动

**背景：** 当前 `git status` 里混了三种变更：
1. Claude 做的插件归档（23 个 R 重命名）
2. 一堆不该追踪的日志/状态文件被改动
3. README、.gitignore、hermes-config 等业务配置变动

**要做：**
1. 先处理 Task 2（清 .gitignore），让噪音消失
2. 第一个 commit：**只** 提交插件归档（P2 的成果）
   ```bash
   git add astrbot/plugins/_archived astrbot/plugins/
   git add SESSION_HANDOFF.md
   git commit -m "chore: archive dead OpenClaw/marketing plugins depending on jw_claw"
   ```
3. 第二个 commit：业务配置/README 的改动（用户明确意图的那些）
4. 跳过：日志、state.db、sessions/ 这类运行时文件

**验收：** 两个清晰的 commit；`git log --oneline -5` 看起来干净。

**注意：** 不要 `git push`，也不要 `--amend`。

### 需要用户确认：当前工作区混有大量未由本任务产生的已修改/未跟踪文件，其中还包含禁区 `SESSION_HANDOFF.md`。如果现在直接分拆 commit，容易误收用户/Claude 的在制改动；建议先确认是否允许我只提交“本轮任务产生的改动”，并继续跳过禁区文件。

---

## [x] Task 6 — 给 Claude 预整理 Router 参考资料

**背景：** Claude 下一步要做 P3 Router（意图分类）。可以提前把分类来源列好，省 Claude 搜索时间。

**要做：** 扫读这些文件，提取「可能需要被 Router 识别为任务」的关键词/命令前缀，输出到 `ROUTER_INTENTS_DRAFT.md`：

- `astrbot/builtin_stars/builtin_commands/commands/harness.py` — `/task` 家族
- `astrbot/core/harness/workflows.py` — `HarnessWorkflowKind` 的 4 种
- `astrbot/plugins/hermes_bridge/__init__.py` — 桥接时匹配的模式
- `astrbot/plugins/dreamina_plugin/` — 图片生成触发词
- `hermes-config/skills/` 的 `SKILL.md` 索引 — 有哪些 skill

**输出格式：**
```markdown
# Router Intents — Draft

## 强信号（命令前缀/关键词）
- `/task ...` → harness workflow
- "生成图片" / "画一张" → dreamina
- ...

## 弱信号（需要 LLM 分类）
- "帮我制定..." → 可能是 marketing_plan workflow
- ...

## HarnessWorkflowKind 完整映射
| 关键词 | kind |
|--------|------|
| 本周推广 / 营销计划 | marketing_plan |
| ...
```

**不要**：写任何代码；不要碰 `jw_router` 目录（Claude 会建）。

**验收：** 产出一个可直接给 Claude 抄的参考表。

结果：已产出 `ROUTER_INTENTS_DRAFT.md`，汇总了 `/task` 家族强信号、4 类 `HarnessWorkflowKind` 映射、Dreamina 触发词、Hermes bridge transport signals，以及 `hermes-config/skills/` 的技能索引。

---

## 完成顺序建议

按这个顺序最不容易出乱子：

1. **Task 2** (.gitignore) ← 先做，让后面看 git status 清爽
2. **Task 1** (归档 jw_astrbot_shell) ← 独立
3. **Task 4** (Plugin health report) ← 只读，安全
4. **Task 6** (Router intents 整理) ← 只读，给 Claude 提供燃料
5. **Task 3** (删过期 migration 文档) ← 判断性的
6. **Task 5** (分拆 commit) ← **最后做**，等前面都尘埃落定

---

## 给 GPT 的规则

- ❌ 不要改 `astrbot/core/harness/**` 任何文件
- ❌ 不要 `git push`、`git reset --hard`、`git commit --amend`、`git rebase`
- ❌ 不要删 `hermes-config/` 下任何配置（只改 .gitignore）
- ❌ 不要动 `SESSION_HANDOFF.md` 除非 Task 5 的 commit 需要 stage 它
- ✅ 每个任务做完在这个文件里打 `[x]` 并写一行结果
- ✅ 遇到任何歧义，**停下来** 在本文件 Task 末尾加 `### 需要用户确认：...`
