# P3 Router 实现 — Qwen 辅助任务
_生成：2026-04-18_
_目标：测试、文档、集成验证。用免费 token，做高杠杆的支撑工作。_

---

## 背景

GPT 做核心实现（Task 1-4），Qwen 做：
- 单元测试覆盖
- 集成测试验证
- 配置示例与文档
- 边界情况发现

---

## 🟢 Task 1 — Router 单元测试框架

**文件位置：** `tests/unit/test_router_intents.py`（新建）

**要做：**
1. 导入 Router 相关类：
   ```python
   import pytest
   from astrbot.core.router import IntentRouter, Intent
   ```

2. 写 fixture：
   ```python
   @pytest.fixture
   async def router():
       config = load_router_config("astrbot/core/router_config.yaml")
       llm_provider = MockLLMProvider()  # 或真实 provider
       return IntentRouter(config, llm_provider)
   ```

3. 写测试用例（覆盖所有分支）：

   **规则匹配测试：**
   - [ ] test_task_new_command — `/task new` 应识别为 task_new
   - [ ] test_task_intake_marketing_plan — `/task intake marketing_plan ...` 应映射到 workflow_kind
   - [ ] test_dreamina_intent — 包含"生成图片"应识别 dreamina_plugin
   - [ ] test_github_intent — 包含"GitHub"应识别 github skill
   - [ ] test_ls_task_command — `/task ls` 应识别为 task_list

   **LLM 分类测试：**
   - [ ] test_ambiguous_message_llm_fallback — 模糊消息应触发 LLM 分类
   - [ ] test_llm_returns_task_intent — LLM 分类结果应正确解析为 Intent
   - [ ] test_llm_returns_conversation — LLM 返回对话应正确标记

   **边界与错误：**
   - [ ] test_empty_message — 空消息如何处理
   - [ ] test_very_long_message — 超长消息截断或处理
   - [ ] test_special_characters — 含特殊字符的消息
   - [ ] test_multiple_intents — 消息可能匹配多个意图（如 GitHub issue + marketing），返回最高置信度的

4. **每个测试的结构：**
   ```python
   @pytest.mark.asyncio
   async def test_xxx(router):
       message = "..."
       context = {}
       intent = await router.classify(message, context)
       
       assert intent.category == "expected_category"
       assert intent.intent_type == "expected_type"
       assert intent.confidence >= 0.7  # 或适当阈值
       if intent.workflow_kind:
           assert intent.workflow_kind in ["marketing_plan", "content_delivery", ...]
   ```

**输出：** `tests/unit/test_router_intents.py`，至少 15 个 test case

**验收：** `pytest tests/unit/test_router_intents.py -v` 全部通过

---

## 🟢 Task 2 — Router 集成测试（与 Harness）

**文件位置：** `tests/integration/test_router_harness_integration.py`（新建）

**要做：**
1. 验证 Router 输出能被 Harness 正确接收：
   ```python
   @pytest.mark.asyncio
   async def test_task_intent_creates_harness_task(router, harness_engine):
       message = "/task intake marketing_plan 本周推广方案"
       intent = await router.classify(message)
       
       # 若是 task intent，创建 Harness task
       if intent.category == "task":
           task = await harness_engine.create_task(
               workflow_kind=intent.workflow_kind,
               title=message,
               ...
           )
           assert task.status == "pending"
           assert task.payload["workflow_kind"] == "marketing_plan"
   ```

2. 验证多次交互的一致性：
   - [ ] test_user_says_task_1_then_list — 先创建任务，再列表
   - [ ] test_task_completeness_flow — 任务从创建 → 完成的完整流程

3. 验证 Router 是否遗漏了任何实际使用场景

**输出：** `tests/integration/test_router_harness_integration.py`（5-10 个 test case）

---

## 🟢 Task 3 — 配置示例与说明文档

**文件位置：** `astrbot/core/router_examples.md`（新建）

**要做：**
1. 写 Router 配置的详细说明（中文）：
   ```markdown
   # Router 配置说明
   
   ## 规则匹配的三层优先级
   
   1. **命令前缀匹配**（最高）
      - `/task new` → task_new
      - 优点：精确、无误
      - 例：`/task intake marketing_plan ...`
   
   2. **关键词列表匹配**（中等）
      - 包含"生成图片"、"画图"等 → dreamina
      - 优点：灵活、用户友好
      - 例："帮我生成一张海报图片"
   
   3. **LLM 分类**（最后）
      - 前两层都未匹配 → 调用 LLM
      - 优点：处理复杂、多义消息
      - 成本：额外一次 API 调用
   
   ## 如何扩展：添加新的 workflow kind
   
   1. 在 `router_config.yaml` 里加新规则
   2. 添加对应的测试用例
   3. 在 Harness.workflows 里已定义（不需改）
   ```

2. 写使用示例：
   ```yaml
   # 示例 1：用户想创建营销计划任务
   用户输入："/task intake marketing_plan 5月促销"
   Router 输出：Intent(category="task", intent_type="marketing_plan", confidence=0.95)
   Harness 动作：创建 marketing_plan workflow 任务
   
   # 示例 2：用户想生成图片
   用户输入："帮我画一张产品效果图"
   Router 流程：
     - 规则匹配：未匹配
     - LLM 分类：返回 Intent(category="skill", skill_name="dreamina", confidence=0.88)
   Hermes 动作：触发 dreamina 生成图片
   
   # 示例 3：普通对话
   用户输入："你好，最近怎么样"
   Router 输出：Intent(category="conversation", confidence=1.0)
   AstrBot 动作：走正常 LLM 对话
   ```

3. 写"如何调试 Router"指南：
   - 打开 debug log（看 Router 规则匹配过程）
   - 单独测试一条规则
   - 检查 LLM 分类的 system prompt 是否清晰

**输出：** `astrbot/core/router_examples.md`（1000+ 字的详细文档）

---

## 🟢 Task 4 — 烟雾测试与边界检验

**即时执行（无输出文件，结果记录在 QWEN_P3_REPORT.md）**

**要做：**
1. 运行以下场景，记录 Router 的实际行为：

   ```
   场景 1：/task 家族的所有子命令
   - /task new → ✓/✗ intent?
   - /task ls → ✓/✗ intent?
   - /task show xxx → ✓/✗ intent?
   - /task start xxx → ✓/✗ intent?
   - /task done xxx summary → ✓/✗ intent?
   - /task fail xxx reason → ✓/✗ intent?
   
   场景 2：四种 workflow kind
   - "帮我制定本周推广计划" → marketing_plan?
   - "把这些内容整理成交付物" → content_delivery?
   - "帮我追踪这个项目进度" → project_followup?
   - "这个需要批准吗" → approval_request?
   
   场景 3：Dreamina 触发词
   - "生成一张海报" → dreamina?
   - "画个 UI 原型" → dreamina?
   - "做成动画" → dreamina?
   
   场景 4：边界情况
   - "" （空消息） → 如何处理？
   - "asdfasdfasdfasdfasdf" （乱码） → 如何处理？
   - "我想要一个 Router 来处理消息" （提到 Router 但实际是对话） → conversation?
   - "/task intake unknown_workflow" （不存在的 workflow） → 错误处理？
   ```

2. 对每个场景记录：
   - 输入
   - 实际输出（Intent）
   - 是否符合预期
   - 若不符合，原因是什么

3. 产出 `QWEN_P3_REPORT.md`：
   ```markdown
   # Router 烟雾测试与边界检验报告 — 2026-04-18
   
   ## 场景 1：/task 子命令
   | 输入 | 期望 Intent | 实际 Intent | ✓/✗ | 备注 |
   |------|------------|-----------|-----|------|
   | /task new | task_new | ? | ? | |
   ...
   
   ## 发现的问题
   - 问题 1：...（说明可复现的步骤）
   - 问题 2：...
   
   ## 建议（给 Claude/GPT 看）
   - 修复建议 1
   - 修复建议 2
   ```

---

## 🟢 Task 5 — 覆盖率分析（可选加分）

**若还有 token，选做：**
1. 跑 `pytest --cov=astrbot.core.router tests/unit/test_router_intents.py`
2. 找出未覆盖的分支（行号）
3. 补充测试或建议 GPT 补充代码

**输出：** `QWEN_P3_COVERAGE_REPORT.md`（可选）

---

## 执行顺序

1. **Task 1** — 写测试框架（15-20m，不依赖 GPT 完成）
2. **Task 2** — 集成测试（依赖 GPT Task 1 完成后，10-15m）
3. **Task 3** — 文档示例（独立，15-20m）
4. **Task 4** — 烟雾测试（依赖 GPT Task 3 完成，20-30m）
5. **Task 5** — 覆盖率（可选，5-10m）

**总计：60-95 分钟**（不计 Task 5）

---

## 验收标准

- [ ] 15 个以上单元测试全部通过
- [ ] 集成测试通过（Router → Harness 流转正确）
- [ ] 文档清晰，可外传
- [ ] 烟雾测试覆盖全部 4 类场景，问题单列
- [ ] 若发现 bug，记录在报告里（由 GPT 后续修）

---

## 禁区

- ❌ 不要改 Router 核心逻辑（Task 1-4 GPT 在做）
- ❌ 不要 git commit（只产出报告）
- ✅ 可以新建测试文件
- ✅ 可以测试失败，记录问题即可
