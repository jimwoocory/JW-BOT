# P3 GPT 最终补完清单
_生成：2026-04-18 | 接手 Qwen 的任务 + 补 Task 3_
_Qwen 已离线，由 GPT 完成剩余工作。预计 60-90 分钟。_

---

## 🔴 Task 3（原计划）— Pipeline 集成 [关键路径]

**状态：** 未完成（git 无相关 commit）

**要做：**
1. 在 AstrBot pipeline 中插入 Router stage
   - 位置：早于 LLM 调用（在 waking check 后）
   - 参考文件：`astrbot/core/pipeline/astr_main_agent.py` 或新建 `astrbot/core/pipeline/router_stage.py`

2. 实现 Router 决策分支：
   ```python
   intent = await router.classify(message, context)
   
   if intent.category == "task":
       # 创建 Harness task
       task = await harness_engine.create_task(
           workflow_kind=intent.workflow_kind,
           title=message[:100],
           ...
       )
       return TaskCreatedResponse(task)
   
   elif intent.category == "skill":
       # 触发对应 skill（TODO：实装）
       return await trigger_skill(intent.skill_name, message)
   
   else:  # "conversation"
       # 正常 LLM 流程
       return await llm_pipeline.respond(message)
   ```

3. 错误处理：Router 异常 → fallback 到对话

**输出：** 修改后的 pipeline（1 个 commit）

**验收：** 消息能正确流转，无 blocking error

---

## 🔴 Task 5（从 Qwen 接手）— IntentRouter 单元测试

**状态：** 缺失（Qwen 误做了 SessionRouter 测试）

**要做：**
1. 新建 `tests/unit/test_intent_router.py`

2. 写单元测试（覆盖所有分支）：

   **规则匹配（高置信度）：**
   ```python
   @pytest.mark.asyncio
   async def test_task_new_command():
       router = IntentRouter.from_yaml(...)
       intent = await router.classify("/task new", {})
       assert intent.category == "task"
       assert intent.intent_type == "task_new"
       assert intent.confidence == 0.95
   
   @pytest.mark.asyncio
   async def test_task_intake_marketing_plan():
       intent = await router.classify("/task intake marketing_plan 本周推广", {})
       assert intent.category == "task"
       assert intent.workflow_kind == "marketing_plan"
   
   @pytest.mark.asyncio
   async def test_dreamina_image_intent():
       intent = await router.classify("帮我生成一张海报", {})
       assert intent.category == "skill"
       assert intent.skill_name == "dreamina_plugin"
   ```

   **LLM 分类（低置信度 fallback）：**
   ```python
   @pytest.mark.asyncio
   async def test_ambiguous_message_llm_fallback():
       # 创建 mock LLM provider
       mock_llm = AsyncMock(return_value='{"category":"task","intent_type":"marketing_plan"}')
       router = IntentRouter(config, llm_provider=mock_llm)
       
       intent = await router.classify("帮我制定推广方案", {})
       assert intent.category == "task"
       mock_llm.assert_called_once()
   ```

   **边界情况：**
   ```python
   @pytest.mark.asyncio
   async def test_empty_message():
       intent = await router.classify("", {})
       assert intent.category == "conversation"  # 默认
   
   @pytest.mark.asyncio
   async def test_very_long_message():
       long_msg = "a" * 10000
       intent = await router.classify(long_msg, {})
       # 应该不崩溃，返回某个 intent
       assert isinstance(intent, Intent)
   ```

3. 至少 15 个 test case

**输出：** `tests/unit/test_intent_router.py`（1 个新文件）

**验收：** `pytest tests/unit/test_intent_router.py -v` 全通过

---

## 🟡 Task F（可选但建议）— 修复 channel_directory.json

**背景：** Qwen 的烟雾测试报告发现：hermes_bridge webhook 配置缺失

**要做：**
1. 读 `hermes-config/channel_directory.json`
2. 在 `platforms` 下补 `webhook` 配置：
   ```json
   {
     "updated_at": "...",
     "platforms": {
       ...existing...,
       "webhook": [
         {
           "id": "astrbot_qq",
           "webhook_url": "http://localhost:8644/webhooks/astrbot_qq",
           "description": "AstrBot QQ官方平台桥接"
         }
       ]
     }
   }
   ```

**输出：** 修改后的 `hermes-config/channel_directory.json`（1 个 commit）

---

## 📋 执行顺序

1. **Task 3** — Pipeline 集成（45-60m，关键路径，做完可测）
2. **Task 5** — 单元测试（20-30m，依赖 Task 3 完成后可并行写）
3. **Task F** — channel_directory 修复（5m，可选，最后做）

**总计：70-95 分钟**

---

## ✅ 最终验收标准

- [ ] Task 3：Router 集成到 pipeline，消息流转正确
- [ ] Task 5：15+ 单元测试全通过
- [ ] Task F（可选）：channel_directory.json 包含 webhook 配置
- [ ] git log 有 2-3 个新 commit
- [ ] 无新的 ERROR / WARNING（除了已知的 Python 版本问题）
- [ ] `pytest tests/unit/test_intent_router.py -v` 全通过

---

## 禁区

- ❌ 不要改 Harness 核心
- ❌ 不要改 SESSION_HANDOFF.md
- ✅ 可以修改 pipeline（小心不破坏既有流程）
- ✅ 新建测试文件没问题

---

_准备好了？开始 Task 3！_
