# JW-Bot 系统背景与现状

_最后更新：2026-04-16_

## 系统架构

```
员工/领导 (QQ)
    ↓
AstrBot v4.22.3（消息管道 + 插件系统）
    ↓ hermes_bridge webhook
Hermes Agent（自主开发与自我完善）
    ↓
JW-Bot 代码库 /Users/dianchi/DC-Agent/
```

## 三个 QQ 频道

| 频道 | 人格 ID | 定位 | 模型 |
|------|---------|------|------|
| 癫池-测试 | DevOps_Console | 开发测试，Hermes 主要接入点 | gpt-5.4-nano |
| 癫池1号 | Enterprise_Ops_Kernel | 管理层 | gpt-5.4-nano |
| 癫池-推广01 | Biz_Assistant_Claw | 员工营销 | gpt-5-nano |

## 当前已部署的插件

### dreamina_plugin（即梦 AI）
- 路径：`/Users/dianchi/DC-Agent/data/plugins/dreamina_plugin/main.py`
- 能力：文生图、文生视频、图片转视频
- LLM 工具：`dreamina_generate_image`、`dreamina_animate_image`、`dreamina_generate_video`
- 自然语言命令支持（regex handler）
- 已知问题：ExceedConcurrencyLimit 时有自动重试（最多 3 次）

### marketing_tools
- 路径：`/Users/dianchi/DC-Agent/astrbot/plugins/marketing_tools/main.py`
- 命令：`/mt_marketing`、`/mt_copy`、`/mt_event`、`/mt_pr`、`/mt_analytics`

### openclaw_core_v2 / openclaw_briefing
- 简报系统：每日简报、竞品简报、平台简报
- 命令前缀：`oc2_`、`brief_`

### hermes_bridge
- 路径：`/Users/dianchi/DC-Agent/astrbot/plugins/hermes_bridge/`
- Hermes webhook：`http://localhost:8644/webhooks/astrbot_qq`
- 回调端口：8645

## Harness 系统现状

- **路径**：`/Users/dianchi/DC-Agent/astrbot/core/harness/`
- **现有文件**：`engine.py`、`task_store.py`、`memory_store.py`、`memory_promotion.py`、`cognition.py`、`contracts.py`、`workflows.py`
- **当前阶段**：框架版本，只有基础的任务记录能力
- **尚未实现**：
  - `orchestrator.py` — 任务执行编排器
  - `tool_interceptor.py` — 工具调用拦截器
  - `workflow_engine.py` — 工作流执行引擎
  - `quality_checkpoints.py` — 质量检查点
- **开发计划**：`/Users/dianchi/DC-Agent/harness-engineering-phase1-plan.md`

## 关键路径

| 资源 | 路径 |
|------|------|
| AstrBot 主目录 | `/Users/dianchi/DC-Agent/` |
| AstrBot 运行日志 | `/Users/dianchi/DC-Agent/astrbot.log` |
| AstrBot 错误日志 | `/Users/dianchi/DC-Agent/astrbot.err.log` |
| Hermes workspace | `/Users/dianchi/DC-Agent/hermes-workspace/` |
| Hermes 配置 | `/Users/dianchi/DC-Agent/hermes-config/` |
| AstrBot 数据库 | `/Users/dianchi/DC-Agent/data/data_v4.db` |
| Harness 数据库 | `/Users/dianchi/DC-Agent/data/harness.db` |
| 启动 AstrBot | `cd /Users/dianchi/DC-Agent && ./.venv/bin/python main.py` |

## 已废弃的系统

- **OpenClaw** — 原来的后端能力层，现已确认不再使用。所有插件、人格中的 OpenClaw 相关内容已清理。

## Hermes 接入方式

员工或开发者在「癫池-测试」发消息 → AstrBot hermes_bridge 转发 → Hermes webhook 接收 → Hermes 处理并回调 AstrBot → 消息发回 QQ

目前 hermes_bridge 在所有频道都加载，但只有测试频道（DevOps_Console 人格）明确引导用户使用 Hermes。
