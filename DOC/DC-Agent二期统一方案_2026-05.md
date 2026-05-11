# DC-Agent 二期统一方案

> **决策件**：本文档把上周 Codex 出的[《DC-Agent 二期需求对比报告》](../deliverables/DC-Agent二期需求对比报告.pdf)、本周对老总指定 case 流的落地评估、以及现有 Harness / Router 全栈路线图合并，输出**单页可决策的二期总规划**。
>
> - 报告日期：2026-05-09
> - 适用周期：2026-05-11 ~ 2026-07
> - 上游输入：3 份内部 DOC（Harness 路线图、Router 路线图、Case 落地评估即本文档 §3）+ 1 份 Codex 问卷分析 PDF

---

## 一、一页式决策摘要（给老总）

| 项 | 内容 |
|---|------|
| **二期主题** | 项目执行助手（沿用 Codex 报告定版） |
| **总框架** | 2A 员工可感知 + 2B 系统深度（沿用 Codex 拆分） |
| **本次修订** | 2A 前插一周（G1+G2 + Case 聚合 v0）；2A-3 由"只读"扩为"读+写归档" |
| **总工期** | 6 周 2A + 灰度 1 周 + 2B 持续推进 |
| **首期投入** | 7h 紧急修复 + 12h Case 聚合 = **第一周可完成** |
| **可立刻拍板的事** | "**先做 G1+G2 (7h) → 2A-0 Case 聚合 (1 周) → 按 Codex 时间轴推进 2A → 再 2B**" |

---

## 二、Codex 报告核心结论（保留）

详见 [deliverables/DC-Agent二期需求对比报告.pdf](../deliverables/DC-Agent二期需求对比报告.pdf)。摘要：

- 11 份问卷，5 类部门（品宣 / 中台 / 执行 / 财务 / 其他），数据时间 2026-05-08
- **2A 员工可感知**：① 项目群聊总结 82% ② 任务提取提醒 91% ③ 飞书资料查询 82%/73% ④ 内容/方案生成模板 55-64% ⑤ 低打扰交互（高强度需求）
- **2B 系统深度**：Harness 满意度、Hermes 升级、知识库记忆、多任务分流、失败重试
- **定版结论**：二期不推翻 Claude Code 方案，**调整交付顺序**——先做员工高频痛点，再上底层深度执行能力

---

## 三、Case 流的"自上而下"验证

老总给出的真实 case：现场沟通 → 飞书 bot 出初稿 → 回公司终稿 → 远程会议 → 多轮修改 → 团队让 Hermes 来 → 深度分析 → 定稿 → 飞书 KB 归档。

### 3.1 Case 9 步 ↔ Codex 2A/2B 映射

| Case 步骤 | Codex 模块 | 现系统 | 评级 |
|----------|-----------|--------|------|
| 1 现场沟通 | — | — | — |
| 2 现场出初稿（图/文） | 2A-4 内容生成模板 | dreamina ✅ + 飞书 ✅ | 🟡 缺打包交付 |
| 3 回公司接续上次数据 | **缺：Case 聚合层** | Harness 有 task，但**无 case 视图** | 🔴 |
| 4 远程会议 | 2A-1 项目群聊总结 | 飞书群 ✅ | 🟡 缺会议笔记 |
| 5 多轮修改 | 2A-1 + 2A-4 | LLM 多轮 ✅ | 🔴 缺版本 |
| 6 团队让 Hermes 来 | 2B Hermes 升级调度 | 关键词识别 ✅ 但**派发依赖满意度，不真发** | 🔴 G1 |
| 7 Hermes 深度分析 | 2B 同上 | Hermes ✅ 但**回群通路是 TODO** | 🔴 G2 |
| 8 团队继续 | — | — | — |
| 9 定稿入 KB | 2A-3 飞书资料查询（**只读**）| 4 路 KB ✅ 但**没 case 归档命令** | 🔴 G4 |

### 3.2 Case 评估给 Codex 报告补的 3 件事

**① G1+G2 必须前置到 2A 之前**

Codex 把"Hermes 升级"放在 2B（06-16 起），但 case Step 6-7 是 2A 阶段就会发生的场景——团队负责人在群里说"让 hermes 来"。规则层已经识别 (`router_config:14-21`，conf 0.98)，但 `RouterStage._handle_task_intent` 不会把它直发给 Hermes，且 Hermes 干完没法回群（`_send_to_qq` 是 TODO）。**两件加起来 7h**：

- **G1**：`_handle_task_intent` 检测 `intent_type=="hermes_escalation"` 时直通派发（3h）
- **G2**：`hermes_bridge._send_to_qq` 实装 + 重试 + DLQ（4h，即 Harness 路线图 Phase 0.3）

**② 新增 2A-0：Case 聚合层 v0（Codex 完全没覆盖）**

Codex 的 2A 四件是**功能点**，case 是**业务流**。功能点串不成流。必须新增一个"Case 概念"作为容器：

- 一个 Case = N 个 Harness task + 关联可交付物（图/文/PPT/视频） + 角色（业务/执行/设计/文案/负责人/甲方） + 版本号 + 状态机（initiated → drafting → reviewing → escalated → archived）
- 最小 CLI：`/case new <name>` `/case context` `/case archive` `/case list`
- 数据：复用 Harness task store，新增 `case_id` 维度
- 工时：**~12h（1 周内）**

**③ 2A-3 改名"飞书资料读+写"，含归档闭环（G4）**

Codex 2A-3 是"飞书资料查询" = 只读。但 case Step 9 要回档进 KB = 写。读和写必须同期做，否则 2A-3 后还得回炉。

- 增加：`/case archive` 把可交付物按 NAS 命名空间写盘 → watchdog 自动入 KB（8h）

---

## 四、统一后的时间轴

```
W0  05-11~05-13 (本周)  G1+G2 (7h) + 2A-0 Case 聚合 v0 (12h)
    └─ 验收：team_leader 群里说"让Hermes来" → 真派发 → Hermes 干完结果回群
              `/case new` 能开一个 case，关联多 task

W1  05-14~05-20         2A-1 项目群聊总结 (沿用 Codex)
    └─ 验收：群里 @DC-Agent 出客户反馈 / 老板要求 / 执行问题 / 阶段结论 四段总结

W2  05-21~05-27         2A-2 任务提取和提醒 (沿用 Codex)
    └─ 验收：负责人、截止时间、待办状态识别落 case-level 台账

W3  05-28~06-03         2A-3 飞书资料读+写（修订自 Codex 2A-3）
    └─ 验收：首批飞书文档+表格+客户资料白名单可查 + `/case archive` 入 KB 闭环

W4  06-04~06-10         2A-4 内容与方案生成模板 (沿用 Codex)
    └─ 验收：客户提案大纲 / 短视频脚本 / 口播 / 小红书 / 朋友圈 / 活动方案六板

W5  06-11~06-17         灰度验收 + 2B 接入评估 (沿用 Codex)
    └─ 选 2-3 个真实项目群灰度，给 2B 选准入门户

W6+ 06-18 起            2B 系统深度（按 Harness 路线图 Phase 1-4 推进）
    └─ Harness 多轮 loop、Planner、Sub-agent、记忆三层、OctoBench-DC、Permission DSL
```

**关键变化**（对照 Codex 时间轴）：
- 插入 W0：G1+G2 + Case 聚合（解锁老总 case 流）
- 2A-3 从只读改为读+写（含归档）
- 总周期延 1 周（4→5 周 2A + 1 周灰度 + 2B 持续）

---

## 五、2B 与 Harness/Router 路线图的对齐

W6+ 开始的 2B 不是从零开发，而是按已有的两份工程路线图推进：

| Codex 2B 模块 | 对应 Harness/Router 路线图项 | 优先级 |
|--------------|-------------------------------|--------|
| Harness 满意度判定 | 已就绪（`satisfaction.py`） | — |
| Hermes 升级调度 | Harness Phase 0.3（G2 提前做完）+ Phase 1.3 sub-agent | P0 |
| 知识库 / 记忆注入 | Harness Phase 2.1-2.5（mem0 三层 + KB retriever） | P0 |
| 多任务分流 | Harness Phase 1.1-1.3（loop + Planner + Sub-agent） + Case 聚合扩展 | P0 |
| 失败重试 | Harness Phase 0.3（G2） + Phase 4.2 HITL | P1 |
| 评测 / 可观测 | Harness Phase 3 (OctoBench-DC) + Router R0 (已完成) | P0 |
| 安全治理 | Harness Phase 4.1（Permission DSL） | P2 |
| 路由分流升级 | Router R1-R5（嵌入分类器 + Rule Editor + Skill Marketplace） | P1-P2 |

**已完成的 2B 地基**（截至本报告日期）：
- [✅] Router R0.1 trace span（[commit 3c074fc1c](https://github.com)）
- [✅] Router R0.2 jsonl 决策日志（同上）
- [✅] Router R0.5 bench v0 + R0.6 CI 阈值（[commit 287e815b4](https://github.com)）
- [✅] Harness sensor 硬化：错误响应不再污染长期记忆（[commit ce9445610](https://github.com)）

---

## 六、立刻可决策的事

请老总今天 / 明天拍板以下三项，开 W0 工单：

1. **同意 G1+G2 + Case 聚合 v0 前置**（W0 共 19h，本周内完成）  → [ ] Yes / [ ] No
2. **2A-3 改名"飞书资料读+写"，含归档闭环 G4**  → [ ] Yes / [ ] No
3. **2B 启动门设在 06-18，参照 Harness/Router 路线图节奏**  → [ ] Yes / [ ] No

---

## 七、文档关系图

```
                  ┌──────────────────────────────┐
                  │ DC-Agent 二期统一方案 (本文)  │ ← 给老总
                  │ Codex + Case + 两份路线图合并 │
                  └──────────────┬───────────────┘
                                 │
        ┌────────────────┬───────┴────────┬─────────────────┐
        ▼                ▼                ▼                 ▼
┌──────────────┐ ┌────────────────┐ ┌──────────────┐ ┌──────────────┐
│ Codex 二期   │ │ Case 落地评估   │ │ Harness 路线 │ │ Router 路线  │
│ 需求对比 PDF │ │ (本文 §3)       │ │ 图           │ │ 图           │
│ (问卷输入)   │ │ (老总 case)     │ │ (工程深度)   │ │ (工程深度)   │
└──────────────┘ └────────────────┘ └──────────────┘ └──────────────┘
   2026-05-08       2026-05-09         2026-05-09        2026-05-09
```

---

## 八、参考文献

### 内部
- [deliverables/DC-Agent二期需求对比报告.pdf](../deliverables/DC-Agent二期需求对比报告.pdf) — Codex 问卷分析 (2026-05-08)
- [DOC/Harness工程演进评估与全栈开发路线图_2026-05.md](Harness工程演进评估与全栈开发路线图_2026-05.md)
- [DOC/Router工程评估与下一步开发计划_2026-05.md](Router工程评估与下一步开发计划_2026-05.md)
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md)
- [SESSION_HANDOFF.md](../SESSION_HANDOFF.md)

### 关键代码锚点（W0 实施时直接打开）
- G1：[astrbot/core/pipeline/process_stage/router_stage.py:127](../astrbot/core/pipeline/process_stage/router_stage.py)
- G2：[astrbot/plugins/hermes_bridge/](../astrbot/plugins/hermes_bridge/)
- Case 聚合 v0：新增 `astrbot/core/case/` 包，复用 `astrbot/core/harness/` 数据模型

---

> **行动信号**：本文档落地后请回复"开 W0"——我立刻拉起 G1 工单，预计本周内完成 G1+G2+Case 聚合 v0 三件。
