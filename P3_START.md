# P3 Router 实现 — 启动指南
_分工：GPT 核心实现 + Qwen 测试与验证_

---

## 🎯 目标

实现消息意图分类 Router：

```
用户消息
    ↓
Router.classify() 
    ├─ 规则匹配（命令、关键词）
    ├─ LLM 分类（低置信度fallback）
    └─ 返回 Intent(category, intent_type, workflow_kind?, skill_name?)
    ↓
上层决策
    ├─ "task" → Harness 创建任务
    ├─ "skill" → 触发对应 skill/Hermes
    └─ "conversation" → LLM 对话
```

---

## 📋 分工

### GPT 做这些（核心）

**读这个：** [`P3_GPT_TASKS.md`](P3_GPT_TASKS.md)

**4 个任务：**
1. **Task 1** — Router 核心类（IntentRouter、Intent、规则匹配、LLM 分类）
2. **Task 2** — Router 配置文件（router_config.yaml）
3. **Task 3** — 集成到 AstrBot pipeline
4. **Task 4** — 设计文档

**预计：** 110-155 分钟

**关键输出：**
- `astrbot/core/router.py` — Router 类（重点）
- `astrbot/core/router_config.yaml` — 规则集
- 修改 pipeline 集成
- `astrbot/core/ROUTER_DESIGN.md` — 文档

---

### Qwen 做这些（辅助）

**读这个：** [`P3_QWEN_TASKS.md`](P3_QWEN_TASKS.md)

**5 个任务（可选 Task 5）：**
1. **Task 1** — 单元测试框架（test_router_intents.py）
2. **Task 2** — 集成测试（with Harness）
3. **Task 3** — 配置示例与文档
4. **Task 4** — 烟雾测试与边界检验（输出报告）
5. **Task 5** — 覆盖率分析（可选）

**预计：** 60-95 分钟

**关键输出：**
- `tests/unit/test_router_intents.py` — 15+ 单元测试
- `tests/integration/test_router_harness_integration.py` — 集成测试
- `astrbot/core/router_examples.md` — 使用示例
- `QWEN_P3_REPORT.md` — 烟雾测试报告

---

## 📚 参考资料（已产出）

| 文件 | 用途 |
|------|------|
| `ROUTER_INTENTS_DRAFT.md` | 强信号命令、workflow kind、skills 索引 |
| `SKILLS_AUDIT.md` | 26 个 skills 健康状态（0 死依赖）|
| `CHANNEL_REPORT.md` | 频道配置结构 |
| `STARTUP_REPORT.md` | 5 个插件、8 个 provider 状态 |
| `test_harness_memory_extra.py` | 10 个 memory 测试 stub（可参考结构）|

---

## 🚀 执行顺序建议

**并行（Qwen 可提前启动）：**
1. Qwen Task 1 — 写单元测试框架（不依赖 GPT）
2. Qwen Task 3 — 写文档示例（不依赖 GPT）
3. GPT Task 1 — 实现 Router 核心（主线）

**顺序（依赖关系）：**
4. GPT Task 2 — 配置文件（依赖 Task 1）
5. Qwen Task 2 — 集成测试（依赖 GPT Task 1）
6. GPT Task 3 — Pipeline 集成（依赖 Task 1-2）
7. Qwen Task 4 — 烟雾测试（依赖 GPT Task 3 完成）
8. GPT Task 4 — 文档完善（最后，基于所有产出）

---

## ✅ 成功标志

### GPT 完成时：
```bash
$ ls astrbot/core/router.py
✓ 存在

$ python -c "from astrbot.core.router import IntentRouter; print('✓ Router 类可导入')"
✓ Router 类可导入

$ pytest tests/unit/test_router_intents.py -v
✓ 15+ tests passed

$ git log --oneline -3
[新 1-2 个 commit 用于 Router]
```

### Qwen 完成时：
```bash
$ pytest tests/unit/test_router_intents.py tests/integration/test_router_harness_integration.py -v
✓ 所有测试通过

$ ls QWEN_P3_REPORT.md
✓ 烟雾测试报告产出

$ ls astrbot/core/router_examples.md
✓ 文档就位
```

### 整体完成时：
- `git status` 干净（仅有 router 相关的新文件/commit）
- 可以推进 P4（可选，比如 Router UI dashboard）
- 或者跑完整系统测试验证消息流转

---

## 🎲 Q&A

**Q: 我是 GPT，不知道怎么开始？**  
A: 从 P3_GPT_TASKS.md 的 Task 1 开始，照着模板写 IntentRouter 类。参考 ROUTER_INTENTS_DRAFT.md 的规则。

**Q: 我是 Qwen，能同时做 Task 1 和 3 吗？**  
A: 完全可以！它们独立，并行做会更快。Task 2 和 4 需要等 GPT 完成才能做。

**Q: 如果 Router 的某个分支测试失败？**  
A: 记录在 QWEN_P3_REPORT.md 的"发现的问题"里，给 GPT 看，GPT 后续修。

**Q: 我想看 Intent 数据结构长什么样？**  
A: P3_GPT_TASKS.md Task 1 的示例代码有定义。

**Q: 规则集应该有多详细？**  
A: 至少覆盖 P3_GPT_TASKS.md Task 2 提到的 20 个意图，初稿够用。后续可以扩充。

**Q: Pipeline 集成很复杂吗？**  
A: 取决于当前 pipeline 结构。参考 P3_GPT_TASKS.md Task 3 的示例，通常就是加一个 stage，转发消息。Qwen 的集成测试能验证是否成功。

---

## 📞 检查清单（开始前）

- [ ] 我读过 P3_GPT_TASKS.md 或 P3_QWEN_TASKS.md（对应）
- [ ] 我知道 Intent 数据结构长什么样
- [ ] 我知道强信号（命令）和弱信号（LLM）的区别
- [ ] 我知道 workflow_kind 有 4 种（在 ROUTER_INTENTS_DRAFT.md）
- [ ] 我知道禁区（不要改 Harness、不要改 SESSION_HANDOFF）
- [ ] git status 干净（或只有我要做的改动）

---

_准备好了？开始吧！_  
_—— Claude Haiku，协调员_
