# 推广团队集成工具 + OpenCLI

结合 OpenCLI 的搜索能力和推广团队集成工具的营销能力，打造面向推广团队的研究型营销助手。

当前这组命令也已经接入 `JW-Claw Harness`：

- 命令入口仍然保持 `/mtoc_*`
- 规划与执行由 Harness 主链负责
- `opencli` 作为营销研究工具被调度
- 当实时 OpenCLI 不可用时，会自动回退到模板/搜索摘要路径

## 核心功能

### 1. 热点营销策划
优先走 OpenCLI 搜索热点话题，再由 Harness 生成基于热点的营销方案

### 2. 竞品分析
优先走 OpenCLI 搜索竞品信息，再由 Harness 生成竞品分析报告

### 3. 新闻营销
优先走 OpenCLI 搜索行业新闻，再由 Harness 生成新闻营销文案

### 4. 数据收集
优先走 OpenCLI 收集市场数据，再由 Harness 进行数据分析

## 使用方式

通过 AstrBot 的 QQ 机器人使用：
- `/mtoc_help` - 查看帮助
- `/mtoc_hot` - 热点营销策划
- `/mtoc_competitor` - 竞品分析
- `/mtoc_news` - 新闻营销
- `/mtoc_data` - 数据收集与分析

## 当前执行说明

这些命令现在不再由插件自己维护一整套独立流程，而是：

1. 插件接收 `/mtoc_*` 请求
2. `HarnessAstrBotBridge` 构造标准输入
3. Planner 生成营销研究步骤
4. Executor 优先尝试 `opencli`
5. 若 OpenCLI 缺失、失败或超时，则自动回退

因此当前真实行为是：

- 可能返回 `OpenCLI 实时搜索结果`
- 也可能返回回退后的模板化营销结果
- 两种结果都会继续走同一条 Harness 链路

## 观察与联动

如果你想看最近是否走了实时搜索、哪些客户和平台最常被搜索，可以配合：

- `/oc2_tasks`
- `/oc2_project_context 柳州五菱`
- `/oc2_project_context 柳汽东风`
- `/oc2_memory_search 小红书`

## 灰度与回退

当 `OPENCLAW_JW_CLAW_HARNESS` 关闭时，`/mtoc_*` 会退回 Legacy 模板响应。

当机器上没有安装 OpenCLI 时，Harness 会自动回退，不会让整条营销命令失败。
