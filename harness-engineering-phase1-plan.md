# Harness Engineering Phase 1 Development Plan

## 目标
验证 Hermes 的代码开发能力，通过实现 Harness Engineering 第一阶段的基础架构，测试其对复杂系统架构的理解和实现能力。

---

## 背景

当前的 Harness 实现只是一个**任务记录系统**（Task Recording System），缺乏真正的工程化能力：

### 现状问题
- ❌ 只在外部被动记录任务状态
- ❌ 没有参与到 Agent 执行循环中
- ❌ 缺少任务规划与分解能力
- ❌ 没有工具调用编排与验证
- ❌ 工作流只是数据模板，没有执行逻辑
- ❌ 缺少质量检查与自动审查机制

### Phase 1 目标
构建 **Harness Orchestrator** 基础框架，实现以下核心能力：
1. ✅ 任务执行编排层
2. ✅ 工具调用拦截与验证
3. ✅ 执行过程自动记录
4. ✅ 基础工作流执行引擎

---

## 开发任务

### Task 1: 创建 Harness Orchestrator 核心类

**文件位置**: `astrbot/core/harness/orchestrator.py`

**任务描述**:
创建一个编排器类，负责协调任务的执行过程。这个类应该：
1. 接收一个 HarnessTask
2. 管理任务的执行状态
3. 协调工具调用
4. 记录执行轨迹

**核心接口**:
```python
class HarnessOrchestrator:
    def __init__(
        self,
        task: HarnessTask,
        engine: HarnessEngine,
        agent: Any,  # MainAgent 或类似对象
    ) -> None:
        """初始化管理器"""
        pass
    
    async def execute(self) -> HarnessTaskResult:
        """执行任务并返回结果"""
        pass
    
    async def record_tool_call(
        self,
        tool_name: str,
        tool_args: dict,
        result: Any,
    ) -> None:
        """记录工具调用"""
        pass
    
    async def validate_execution(self) -> ExecutionValidation:
        """验证执行结果是否符合任务要求"""
        pass
```

**验收标准**:
- [ ] 类结构清晰，职责单一
- [ ] 有完整的类型注解
- [ ] 包含错误处理逻辑
- [ ] 有单元测试覆盖核心方法

---

### Task 2: 实现工具调用拦截器

**文件位置**: `astrbot/core/harness/tool_interceptor.py`

**任务描述**:
创建一个工具调用拦截器，在工具执行前后进行干预：
1. 执行前验证工具调用是否符合任务目标
2. 记录工具调用意图
3. 执行后验证结果有效性
4. 触发质量检查

**核心接口**:
```python
class HarnessToolInterceptor:
    def __init__(
        self,
        orchestrator: HarnessOrchestrator,
        task: HarnessTask,
    ) -> None:
        pass
    
    async def intercept(
        self,
        tool_call: ToolCall,
    ) -> ToolCallResult:
        """拦截工具调用"""
        # 1. 验证工具调用是否偏离任务目标
        # 2. 记录调用意图到 Harness
        # 3. 执行工具
        # 4. 验证结果
        # 5. 返回结果
        pass
    
    def _aligns_with_task(
        self,
        tool_call: ToolCall,
    ) -> bool:
        """检查工具调用是否与任务目标一致"""
        pass
    
    def _validate_result(
        self,
        tool_call: ToolCall,
        result: Any,
    ) -> ValidationResult:
        """验证工具执行结果"""
        pass
```

**验收标准**:
- [ ] 能够拦截工具调用
- [ ] 能够识别偏离任务的工具调用
- [ ] 有完整的日志记录
- [ ] 单元测试覆盖验证逻辑

---

### Task 3: 增强工作流执行引擎

**文件位置**: `astrbot/core/harness/workflow_engine.py`

**任务描述**:
将当前的工作流模板升级为可执行的引擎：
1. 定义工作流执行步骤
2. 实现步骤验证逻辑
3. 自动触发审查条件判断
4. 支持工作流扩展

**核心接口**:
```python
class WorkflowExecutor:
    def __init__(
        self,
        task: HarnessTask,
        orchestrator: HarnessOrchestrator,
    ) -> None:
        pass
    
    async def execute(self) -> WorkflowResult:
        """执行工作流"""
        # 1. 解析工作流类型
        # 2. 获取对应的执行模板
        # 3. 逐步执行
        # 4. 验证每个步骤
        # 5. 判断是否需要审查
        pass
    
    async def _execute_step(
        self,
        step: WorkflowStep,
    ) -> StepResult:
        """执行单个工作流步骤"""
        pass
    
    def _check_review_required(
        self,
        result: WorkflowResult,
    ) -> bool:
        """判断是否需要人工审查"""
        pass
```

**工作流模板示例**:
```python
WORKFLOW_TEMPLATES = {
    "marketing_plan": {
        "steps": [
            {"name": "research", "validator": ResearchValidator()},
            {"name": "strategy", "validator": StrategyValidator()},
            {"name": "channels", "validator": ChannelsValidator()},
            {"name": "compile", "validator": PlanValidator()},
        ],
        "review_conditions": [
            lambda result: result.budget > 100000,
            lambda result: result.channels_count > 5,
        ],
    },
    # ... 其他工作流
}
```

**验收标准**:
- [ ] 支持至少 2 种工作流类型
- [ ] 每个工作流有明确的步骤定义
- [ ] 能够自动判断是否需要审查
- [ ] 有完整的执行日志

---

### Task 4: 集成到 Agent 执行循环

**文件位置**: `astrbot/core/pipeline/process_stage/method/agent_sub_stages/internal.py`

**任务描述**:
修改 `InternalAgentSubStage` 类，使其支持 Harness 编排模式：
1. 检测当前是否有活跃的 Harness 任务
2. 如果有任务，使用 Orchestrator 模式执行
3. 如果没有任务，使用普通对话模式
4. 确保向后兼容

**修改点**:
```python
class InternalAgentSubStage(Stage):
    async def process(self, event: AstrMessageEvent) -> AsyncGenerator:
        # 检查是否有活跃任务
        task = await self.ctx.get_current_harness_task(
            event.unified_msg_origin
        )
        
        if task and task.status not in HARNESS_TERMINAL_STATUSES:
            # 使用 Harness 编排模式
            orchestrator = HarnessOrchestrator(
                task=task,
                engine=self.ctx.harness_engine,
                agent=self.main_agent,
            )
            
            # 设置工具拦截器
            interceptor = HarnessToolInterceptor(
                orchestrator=orchestrator,
                task=task,
            )
            
            # 执行任务
            result = await orchestrator.execute()
            
            # 更新事件结果
            event.set_result(result.to_message())
        else:
            # 普通对话模式（保持现有逻辑）
            yield from (await super().process(event))
```

**验收标准**:
- [ ] 能够检测活跃任务
- [ ] 能够切换到编排模式
- [ ] 普通对话不受影响
- [ ] 有集成测试

---

### Task 5: 添加执行质量检查点

**文件位置**: `astrbot/core/harness/quality_checkpoints.py`

**任务描述**:
实现质量检查机制，在关键节点验证执行质量：
1. 定义检查点接口
2. 实现基础检查器
3. 集成到执行流程
4. 支持自定义检查器

**核心接口**:
```python
class QualityCheckpoint(ABC):
    @abstractmethod
    async def check(
        self,
        context: ExecutionContext,
    ) -> CheckResult:
        """执行检查并返回结果"""
        pass

class TaskAlignmentCheckpoint(QualityCheckpoint):
    """检查执行是否偏离任务目标"""
    async def check(self, context: ExecutionContext) -> CheckResult:
        pass

class ToolUsageCheckpoint(QualityCheckpoint):
    """检查工具使用是否合理"""
    async def check(self, context: ExecutionContext) -> CheckResult:
        pass

class ResultCompletenessCheckpoint(QualityCheckpoint):
    """检查结果完整性"""
    async def check(self, context: ExecutionContext) -> CheckResult:
        pass
```

**验收标准**:
- [ ] 至少实现 3 个检查器
- [ ] 检查器可插拔
- [ ] 检查结果影响任务状态
- [ ] 有单元测试

---

## 测试要求

### 单元测试
- 所有核心类必须有单元测试
- 测试覆盖率 > 80%
- 测试文件位置：`tests/unit/test_harness_orchestrator.py`

### 集成测试
- 创建一个完整的任务执行流程测试
- 模拟真实场景
- 测试文件位置：`tests/integration/test_harness_execution.py`

### 手动测试场景
1. 创建一个营销策划任务
2. 观察工具调用是否被正确拦截
3. 验证执行轨迹是否记录到数据库
4. 检查结果完整性验证

---

## 交付物

### 代码文件
- [ ] `astrbot/core/harness/orchestrator.py`
- [ ] `astrbot/core/harness/tool_interceptor.py`
- [ ] `astrbot/core/harness/workflow_engine.py`
- [ ] `astrbot/core/harness/quality_checkpoints.py`
- [ ] `tests/unit/test_harness_orchestrator.py`
- [ ] `tests/unit/test_harness_tool_interceptor.py`
- [ ] `tests/unit/test_harness_workflow_engine.py`
- [ ] `tests/unit/test_harness_quality_checkpoints.py`

### 文档
- [ ] 更新 `docs/harness-jwbot-landing-plan.md`
- [ ] 添加使用示例
- [ ] 编写 API 文档

### 测试报告
- [ ] 单元测试覆盖率报告
- [ ] 集成测试通过情况
- [ ] 手动测试记录

---

## 评估标准

### 架构设计 (30%)
- 清晰的模块划分
- 合理的抽象层次
- 良好的扩展性设计

### 代码质量 (30%)
- 类型注解完整
- 错误处理完善
- 代码风格一致
- 注释清晰

### 功能完整性 (25%)
- 所有核心功能实现
- 测试覆盖充分
- 文档完整

### 创新性 (15%)
- 解决问题的巧妙方法
- 性能优化
- 用户体验改进

---

## 时间估算

- **Task 1**: 2-3 小时
- **Task 2**: 2-3 小时
- **Task 3**: 3-4 小时
- **Task 4**: 2-3 小时
- **Task 5**: 2-3 小时
- **测试与文档**: 2-3 小时

**总计**: 13-19 小时

---

## 开始指令

请将此 Plan 提供给 Hermes，让它按照以下顺序执行：

1. 首先阅读并理解整个架构
2. 从 Task 1 开始依次实现
3. 每完成一个 Task 提交一次代码
4. 运行测试确保质量
5. 完成后生成总结报告

**提示**: 鼓励 Hermes 在实现过程中提出改进建议，但要确保核心功能优先完成。

---

## 联系信息

如有疑问或需要澄清，请通过以下方式：
- 查看现有 Harness 代码了解设计意图
- 参考 `docs/harness-jwbot-landing-plan.md` 了解整体规划
- 检查测试文件了解预期行为

---

**文档版本**: 2026-04-11  
**适用版本**: JW-Bot v4.22.3+  
**难度等级**: ⭐⭐⭐⭐ (中高难度)
