# P3 Router 实现 — GPT 核心任务
_生成：2026-04-18_
_目标：构建意图分类 Router，连接 AstrBot 消息入口 → Harness workflow / LLM 对话_

---

## 背景

**问题：** 目前 AstrBot 接收到消息后，直接转给 Hermes bridge 或 LLM。没有意图分类，无法区分"这是一个任务"还是"这是一个对话"。

**参考资料已就绪：**
- `ROUTER_INTENTS_DRAFT.md` — 26 个 skills 索引、4 种 workflow kind、强信号命令、弱信号 NLP 触发词
- `SKILLS_AUDIT.md` — skills 健康状态（0 个死依赖）
- `CHANNEL_REPORT.md` — 频道配置结构

**目标：** 实现 Router，使得：
```
消息入口（AstrBot）
    ↓
Router.classify_intent(message)
    ├─ 规则匹配（命令前缀、关键词）→ intent + confidence
    ├─ 低置信度 → LLM 分类（一次额外调用）
    └─ 返回 { intent, confidence, workflow_kind?, skill_name? }
    ↓
上层决策
    ├─ 若 workflow_kind → Harness.create_task(workflow_kind, ...)
    ├─ 若 skill_name → 触发对应 skill 或 Hermes call
    └─ 否则 → 常规 LLM 对话
```

---

## 🔴 Task 1 — Router 核心类实现

**文件位置：** `astrbot/core/router.py`（新建）

**要做：**
1. 定义 `Intent` 数据类：
   ```python
   @dataclass
   class Intent:
       category: str  # "task" / "skill" / "conversation"
       intent_type: str  # "marketing_plan" / "dreamina" / "general"
       confidence: float  # 0-1
       workflow_kind: Optional[str]  # 若 category=="task"
       skill_name: Optional[str]  # 若 category=="skill"
       metadata: dict  # 其他信息
   ```

2. 实现 `IntentRouter` 类：
   ```python
   class IntentRouter:
       def __init__(self, config: dict, llm_provider):
           # config: from ROUTER_INTENTS_DRAFT.md 的规则集
           # llm_provider: 用于弱信号 LLM 分类
       
       async def classify(self, message: str, context: dict) -> Intent:
           """主分类函数"""
           # 1. 规则匹配（高置信度）
           # 2. 若未匹配或低置信度 → LLM 分类
           # 3. 返回 Intent
   ```

3. **规则匹配逻辑**：
   - 检查 `/task` 前缀 → 解析 subcommand（new/ls/start/done 等）
   - 检查 `marketing_plan` / `content_delivery` 等关键词 → 映射到 workflow_kind
   - 检查 `生成图片` / `画图` / `生成视频` 等 → dreamina_plugin
   - Hermes bridge 信号（`session_key` / `platform=qq` 等）→ transport intent
   - 其他 skills 简单匹配（GitHub issue、Google Docs 等）

4. **LLM 分类**（低置信度时触发）：
   - 使用紧凑的 system prompt，告诉 LLM：
     - 可能的 workflow kind 列表
     - 可能的 skill 列表（从 SKILLS_AUDIT 摘要）
     - 若都不匹配 → "conversation"
   - 返回结构化分类结果
   - 解析 LLM 输出为 `Intent` 对象

**输出：** `astrbot/core/router.py`（完整实现）

**测试：** 由 Qwen Task 1 负责写 `test_router_intents.py`

---

## 🔴 Task 2 — Router 配置与规则集

**文件位置：** `astrbot/core/router_config.yaml`（新建）

**要做：**
1. 定义规则集结构（YAML）：
   ```yaml
   task_intents:
     - pattern: "/task new"
       confidence: 0.95
       category: "task"
       intent_type: "task_new"
     
     - pattern: "/task intake marketing_plan"
       confidence: 0.95
       category: "task"
       intent_type: "marketing_plan"
       workflow_kind: "marketing_plan"
   
   skill_intents:
     - keywords: ["生成图片", "画一张", "做一张图"]
       confidence: 0.85
       category: "skill"
       skill_name: "dreamina_plugin"
     
     - pattern: "GitHub"  # 简单 substring 匹配
       confidence: 0.7
       category: "skill"
       skill_name: "github"
   
   # LLM 分类的 system prompt 模板
   llm_fallback:
     system_prompt: |
       你是一个意图分类器。
       用户消息可能属于以下任何一类：
       
       Task 类：...
       Skill 类：...
       Conversation：其他
   ```

2. 从 `ROUTER_INTENTS_DRAFT.md` 摘取规则，转成 YAML（至少覆盖强信号）

**输出：** `astrbot/core/router_config.yaml`

**验收：** 能被 Router 类正确加载和使用

---

## 🔴 Task 3 — 集成入 AstrBot pipeline

**文件位置修改：** `astrbot/core/pipeline/astr_main_agent.py` 或新建 `astrbot/core/pipeline/router_stage.py`

**要做：**
1. 在 pipeline 中插入 Router stage（早于 LLM 调用）：
   ```
   消息到达
       ↓
   [新] Router stage
       ├─ classify_intent()
       └─ 根据 Intent 决策
       ↓
   [现有] LLM stage（仅"conversation" 进入）
       或
   [新] Harness stage（"task" 进入）
       或
   [新] Skill trigger（"skill" 进入）
   ```

2. Router 决策的分支：
   ```python
   intent = await router.classify(message)
   
   if intent.category == "task":
       # 转给 Harness 创建任务
       task = await harness_engine.create_task(
           workflow_kind=intent.workflow_kind,
           title=message[:50],
           ...
       )
       return TaskCreatedResponse(task)
   
   elif intent.category == "skill":
       # 触发对应 skill（或转给 Hermes）
       return trigger_skill(intent.skill_name, message)
   
   else:  # "conversation"
       # 走正常 LLM 对话
       return await llm_agent.respond(message)
   ```

3. 错误处理：
   - Router 异常 → fallback 到对话
   - Intent 边界情况 → 给用户提示

**输出：** 修改后的 pipeline 或新 stage

**验收：** 消息能正确流转，无 blocking error

---

## 🟡 Task 4 — 文档与示例

**文件位置：** `astrbot/core/ROUTER_DESIGN.md` 和示例

**要做：**
1. 写设计文档：
   - 架构图（ASCII 或 mermaid）
   - 分类规则说明
   - LLM fallback 何时触发
   - 扩展点（如何添加新的 skill / workflow kind）

2. 写示例代码：
   - 如何单独测试 Router
   - 如何添加自定义规则
   - 如何集成到其他地方

**输出：** `astrbot/core/ROUTER_DESIGN.md`

---

## ✅ 验收标准

- [ ] `astrbot/core/router.py` 完成（IntentRouter 类、Intent 数据类）
- [ ] `astrbot/core/router_config.yaml` 完成（规则集覆盖至少 20 个意图）
- [ ] Router 集成到 pipeline（消息流转正确，无 blocking）
- [ ] Qwen 的 `test_router_intents.py` 覆盖主要分支
- [ ] 无新的 ERROR / WARNING（除了已知的 Python 版本兼容性问题）
- [ ] 文档完整，可外传

---

## 预计耗时

- Task 1：45-60 分钟
- Task 2：15-20 分钟
- Task 3：30-45 分钟
- Task 4：20-30 分钟

**总计：110-155 分钟**

---

## 禁区

- ❌ 不要改 Harness 核心（engine.py、memory、workflows）
- ❌ 不要改 SESSION_HANDOFF.md
- ❌ 不要改 plugin manager
- ✅ 新建 router.py 和 router_config.yaml 没问题
- ✅ 可以修改 pipeline 但要小心不破坏既有流程
