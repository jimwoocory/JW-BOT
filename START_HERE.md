# 🚀 START HERE — 任务启动指南

_for GPT 和 Qwen_

---

## GPT Round 2 — 你的任务清单

👉 **读这个：** [`GPT_TASKS_ROUND2.md`](GPT_TASKS_ROUND2.md)

**4 个任务，约 40 分钟：**
1. **Task B** — Skills 目录扫描 → `hermes-config/skills/SKILLS_AUDIT.md`
2. **Task E** — Channel 配置校验 → `hermes-config/CHANNEL_REPORT.md`
3. **Task 5** — Git commit 分拆 → 3 个清晰 commit
4. **Task F** — hermes_bridge bug 修 → `astrbot/plugins/hermes_bridge/__init__.py`

**关键规则：**
- ❌ 不碰 `astrbot/core/harness/**`
- ❌ 不碰 `hermes-config/skills/red-teaming/` 任何文件（只读）
- ✅ Task F 是唯一改代码的地方
- ✅ 遇到歧义在输出文件末尾加 `### ❓ 待确认`

**进度追踪：** [`TASK_DASHBOARD.md`](TASK_DASHBOARD.md)

---

## Qwen — 你的任务状态

✅ **已完成：**
- Task A：434 单元测试全通过 → [`TEST_REPORT.md`](TEST_REPORT.md)
- Task C：10 个测试 stub 框架就绪 → [`tests/unit/test_harness_memory_extra.py`](tests/unit/test_harness_memory_extra.py)
- Task D：启动完全正常 → [`STARTUP_REPORT.md`](STARTUP_REPORT.md)

⏹️ **未完成（已转移给 GPT）：**
- Task B → GPT 接手
- Task E → GPT 接手

🎯 **如果还有额度，可做：**
- 在 `tests/unit/test_harness_memory_extra.py` 中补充实现（不只是 pass）
- 运行 `pytest tests/unit/test_harness_memory_extra.py -v` 验证

---

## 上下文文件（都读过吗）

| 文件 | 用途 | 你需要吗 |
|------|------|---------|
| [`SESSION_HANDOFF.md`](SESSION_HANDOFF.md) | P1/P2 核对结论 | 🔵 必读（GPT Task 5） |
| [`SESSION_STATUS.md`](SESSION_STATUS.md) | 整体进度快照 | 🟢 可选（了解背景） |
| [`ROUTER_INTENTS_DRAFT.md`](ROUTER_INTENTS_DRAFT.md) | P3 Router 参考 | 🟢 可选（后续 Claude 用） |
| [`GPT_TASKS.md`](GPT_TASKS.md) | Round 1 完成情况 | 🟢 可选（看 GPT 做了啥） |

---

## 快速检查清单

**开始前：**
- [ ] 我是 GPT 吗？→ 读 `GPT_TASKS_ROUND2.md` 第一页
- [ ] 我是 Qwen 吗？→ 看上面"已完成"和"未完成"
- [ ] 我理解禁区吗？→ 确认不碰红队代码
- [ ] git 状态查过吗？→ `git status` 看一眼，确认清晰

**执行中：**
- [ ] 产出文件名对吗？
- [ ] 格式符合规范吗？
- [ ] 有死依赖吗？能列出来吗？

**完成后：**
- [ ] 产出文件放对位置了吗？
- [ ] 冒烟测试通过了吗？（特别是 Task F）
- [ ] TASK_DASHBOARD.md 更新了吗？

---

## 如果遇到问题

| 问题 | 怎么办 |
|------|--------|
| 不知道从哪开始 | 👉 看本文件上方 |
| SESSION_HANDOFF.md 咋修改的 | 👉 看 `GPT_TASKS_ROUND2.md` 前置条件 |
| red-teaming 里的代码能改吗 | 👉 **不能**，只读分析 |
| Task 5 怎么分 commit | 👉 看 `GPT_TASKS_ROUND2.md` Task 5 的三个范本 |
| hermes_bridge bug 怎么改 | 👉 看 `GPT_TASKS_ROUND2.md` Task F |
| 额度快用完了 | 👉 停止，等另一个接手 |

---

## 成功标志 🎉

### GPT Round 2 全部完成时：
```bash
$ git log --oneline -5
[最新 3 个都来自本 round]
[SESSION_HANDOFF 有更新]
[hermes_bridge/__init__.py 有修复]

$ git status
[干净，无修改中的文件]

$ ls hermes-config/skills/SKILLS_AUDIT.md
[存在，包含 26 个 skills]

$ ls hermes-config/CHANNEL_REPORT.md
[存在，包含校验结果]
```

### 然后 Claude 可以：
✅ 清空 git status  
✅ 启动 P3 Router 实现  
✅ 合并所有报告到 SESSION_HANDOFF.md  

---

_准备好了？开始行动吧！_  
_—— Claude Haiku，任务协调员_
