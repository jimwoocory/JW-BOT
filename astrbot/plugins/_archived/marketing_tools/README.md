# 推广团队集成工具

专门为公司推广团队打造的 AI 助手工具集，集成了品牌营销、文案创作、活动策划、公关管理、数据分析等能力。

当前这组命令已经接入 `JW-Claw Harness`，也就是：

- AstrBot 命令仍然保持 `/mt_*` 入口不变
- 业务执行会优先走 `jw_claw` 新主链
- 当 `OPENCLAW_JW_CLAW_HARNESS` 关闭时，会退回 Legacy 模板响应

## 功能模块

### 1. 品牌营销策划
- 品牌战略规划
- 推广渠道规划
- 内容营销策划
- KOL/网红合作
- 营销活动策划

### 2. 创意文案
- 品牌故事创作
- 社交媒体文案
- 营销文案
- 产品描述
- 广告文案

### 3. 活动策划
- 活动策划
- 路演策划
- 产品发布会
- 展览策划
- 预算管理

### 4. 公关管理
- 媒体关系管理
- 新闻稿撰写
- 危机公关
- 品牌声誉管理
- 采访准备

### 5. 数据分析
- KPI体系设计
- 数据分析
- 效果评估
- ROI计算
- 报告撰写

## 使用方式

通过 AstrBot 的 QQ 机器人使用：
- `/mt_help` - 查看帮助
- `/mt_marketing` - 品牌营销策划
- `/mt_copy` - 创意文案
- `/mt_event` - 活动策划
- `/mt_pr` - 公关管理
- `/mt_analytics` - 数据分析

## 当前执行路径

当前命令由 `marketing_tools` 插件接收后，会交给 `HarnessAstrBotBridge`，再进入：

1. 消息适配
2. 路由与规划
3. 审查与执行
4. 结果格式化

如果你想查看这条新路径的任务和上下文，可以配合：

- `/oc2_tasks`
- `/oc2_project_context <query>`
- `/oc2_memory`
- `/oc2_memory_search <query>`

## 灰度与回退

相关环境变量：

- `OPENCLAW_JW_CLAW_HARNESS`
- `OPENCLAW_JW_CLAW_HARNESS_DEBUG`

当 Harness 关闭时，`/mt_*` 命令仍可返回 Legacy 模板响应，不会直接失效。
