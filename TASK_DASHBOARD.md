# Task Dashboard — 实时进度追踪
_生成：2026-04-18 | 更新者：Claude Haiku_

---

## 🔴 GPT Round 2 — 实时状态

### Task B：Skills Audit（26 个 skills 扫描）
```
📝 分配日期：2026-04-18
🎯 目标文件：hermes-config/skills/SKILLS_AUDIT.md
⏱️  预计耗时：15-20 分钟
📊 进度：[✓] 启动 [✓] 进行中 [✓] 草稿完成 [✓] 审查 [✓] 已完成
```

**要点：**
- 26 个 skills 目录全扫
- 检查 dead imports（jw_claw、绝对路径、openclaw_connector）
- red-teaming/godmode 只读不改
- 输出：表格 + 问题清单

---

### Task E：Channel Directory Validation
```
📝 分配日期：2026-04-18
🎯 目标文件：hermes-config/CHANNEL_REPORT.md
⏱️  预计耗时：10-15 分钟
📊 进度：[✓] 启动 [✓] 进行中 [✓] 草稿完成 [✓] 审查 [✓] 已完成
```

**要点：**
- 读 channel_directory.json 结构
- 校验必填字段、引用完整性
- 找悬空 platform_id、无效 webhook URL、重复 id
- 输出：校验表 + 问题列表

---

### Task 5：Git Commit 分拆（3 个 commit）
```
📝 分配日期：2026-04-18
🎯 目标：git log 清晰，3 个独立 commit
⏱️  预计耗时：5 分钟
📊 进度：[✓] 启动 [✓] 进行中 [✓] 第1个 [✓] 第2个 [✓] 第3个 [✓] 已完成
```

**Commit 清单：**
1. [✓] chore: archive dead OpenClaw plugins and jw_astrbot_shell
2. [✓] chore: remove runtime files from tracking and update .gitignore
3. [✓] docs: update SESSION_HANDOFF with P1 verification results

---

### Task F：hermes_bridge @register Bug Fix
```
📝 分配日期：2026-04-18
🎯 目标文件：astrbot/plugins/hermes_bridge/__init__.py
⏱️  预计耗时：5 分钟
📊 进度：[✓] 启动 [✓] 修复 [✓] 冒烟测试 [✓] 已完成
```

**要点：**
- 补 `version` 参数到 @register
- 冒烟：`python -c "from astrbot.plugins.hermes_bridge import *"`
- Commit 并记录

---

## 🔵 Qwen（已用完，后续接手方案）

### Task B 接手转移？
```
原计划：Qwen Task B — Skills Audit
当前：GPT Round 2 Task B
状态：[✓] 由 GPT 接手
```

### Task E 接手转移？
```
原计划：Qwen Task E — Channel Report
当前：GPT Round 2 Task E
状态：[✓] 由 GPT 接手
```

---

## 🟡 Claude Haiku 待命任务

### 📝 关键路径依赖检查
```
前置条件：GPT Task 5 commit 完成
触发条件：git status 干净
目标：验证所有改动已妥当提交
```

### 📝 填测试 Stub（可提前准备）
```
前置条件：TEST_REPORT 已产出 + test_harness_memory_extra.py 已生成
触发条件：随时可做（独立）
目标：fill `test_harness_memory_extra.py` 的 10 个 async test
预计耗时：20-30 分钟
```

### 📝 P3 Router 实现（后续）
```
前置条件：GPT Task B/E 完成 + Task 5 commit 完成
触发条件：git log 干净、ROUTER_INTENTS_DRAFT.md 就绪
目标：实现意图分类 Router
预计耗时：60+ 分钟
所需：ROUTER_INTENTS_DRAFT.md 作参考
```

---

## 📂 文件组织

### 输入（已准备）
```
GPT_TASKS_ROUND2.md ← GPT 读这个
SESSION_HANDOFF.md ← 上下文
ROUTER_INTENTS_DRAFT.md ← Router 参考
```

### 输出（待填）
```
hermes-config/skills/SKILLS_AUDIT.md ← GPT Task B
hermes-config/CHANNEL_REPORT.md ← GPT Task E
[git commits] ← GPT Task 5
astrbot/plugins/hermes_bridge/__init__.py ← GPT Task F（修改）
```

---

## ⚠️ 风险和注意事项

| 风险 | 缓解措施 |
|------|---------|
| SESSION_HANDOFF.md 改动 | 纳入 Task 5 Commit 3，说明是 P1 核对结果 |
| red-teaming/godmode 修改 | GPT 只读分析，Qwen Task B 中明确禁区 |
| hermes_bridge bug 修复后未冒烟 | Task F 要求冒烟通过再 commit |
| Qwen 额度用尽 | 已转移 Task B/E 给 GPT，GPT 90% 充足 |

---

## 预计完成时间线

```
T+0m   : 任务分配给 GPT + Qwen（现在）
T+15m  : Task B 草稿（Skills Audit）
T+25m  : Task E 完成（Channel Report）
T+30m  : Task 5 完成（3 commit）
T+35m  : Task F 完成（bug fix）
         ↓ 所有产出产生
T+40m  : Haiku 验收 + 整理
T+50m  : 可开始 P3 Router 实现
```

---

## 检查清单

### GPT 行动前
- [ ] 读 GPT_TASKS_ROUND2.md
- [ ] 确认没有 git conflict（git status）
- [ ] 确认禁区文件不碰（red-teaming 等）

### 产出文件生成时
- [ ] SKILLS_AUDIT.md 覆盖 26 个 skills
- [ ] CHANNEL_REPORT.md 校验完整
- [ ] 3 个 commit 各司其职
- [ ] hermes_bridge 冒烟通过

### Haiku 验收时
- [ ] git log --oneline -10 干净
- [ ] git status 仅含预期改动
- [ ] 所有产出文件格式正确
- [ ] 没有新的 ERROR / WARNING

---

_此文件由 Haiku 维护。每有更新在此打勾记录。_
_GPT/Qwen 完成任务后，在对应行修改 `[✓]` 进度条。_

### 2026-04-18 GPT 更新

**[02:17] Task B 完成** — SKILLS_AUDIT.md
- 26 个 skills 全扫 + 80 个 nested SKILL.md
- 0 个死依赖，19 个正常，7 个占位符
- `nas` 有绝对路径耦合（低风险）
- red-teaming/godmode 只读分析完成

**[02:17] Task E 完成** — CHANNEL_REPORT.md  
- channel_directory.json 是空目录（合法状态）
- 建议了后续 schema 规范

**[完成] Task 5**
- 归档、tracking 清理、handoff/docs 已分别落到独立 commit
- 因 `.gitignore` 生效顺序问题，补了一个纠正性 cleanup commit，实际结果已正确

**[完成] Task F**
- `hermes_bridge` 已补齐 `@register(..., "1.0.0")`
- 冒烟通过：`from astrbot.plugins.hermes_bridge import *`
