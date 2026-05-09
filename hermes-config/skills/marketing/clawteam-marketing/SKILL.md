---
name: clawteam-marketing
description: 当收到 marketing_plan 类型的 AstrBot 任务时，使用 ClawTeam 召集三人并行研究团队（调研员、分析师、策略师），完成后汇总结果并回传。
version: 1.0.0
author: JW-Bot
metadata:
  hermes:
    tags: [marketing, clawteam, multi-agent, astrbot, jw-bot]
    related_skills: [hermes-agent]
---

# ClawTeam 营销策划编排 Skill

## 触发条件

当 AstrBot 派发的任务满足以下条件时，使用此 Skill：
- `workflow_kind = marketing_plan`
- 任务描述涉及营销策划、推广方案、渠道规划、品牌传播

## 执行流程

### Phase 1：启动 ClawTeam

```bash
# 1. 创建团队（使用 marketing-research 模板）
clawteam team create jw-marketing --template marketing-research

# 2. 为每个 worker 创建任务
clawteam task create jw-marketing \
  --subject "平台趋势与竞品调研" \
  --owner researcher \
  --priority high

clawteam task create jw-marketing \
  --subject "竞争格局与机会点分析" \
  --owner analyst \
  --priority high

clawteam task create jw-marketing \
  --subject "营销策略与内容规划" \
  --owner strategist \
  --priority high

# 3. 并行启动三个 worker（--source tool 隐藏在 sessions list 中）
clawteam spawn \
  --team jw-marketing \
  --agent-name researcher \
  --cli hermes \
  --message "你的任务：<goal_from_brief>"

clawteam spawn \
  --team jw-marketing \
  --agent-name analyst \
  --cli hermes \
  --message "你的任务：<goal_from_brief>"

clawteam spawn \
  --team jw-marketing \
  --agent-name strategist \
  --cli hermes \
  --message "你的任务：<goal_from_brief>"
```

### Phase 2：等待完成

```bash
# 轮询直到所有任务完成（最长等待 10 分钟）
clawteam task wait jw-marketing --timeout 600

# 或查看实时进度
clawteam task list jw-marketing
```

### Phase 3：读取结果并汇总

Worker 的结果写在各自的工作目录中：
- `~/.clawteam/workspaces/jw-marketing/researcher/research_output.md`
- `~/.clawteam/workspaces/jw-marketing/analyst/analysis_output.md`
- `~/.clawteam/workspaces/jw-marketing/strategist/strategy_output.md`

将三份输出合并成一份完整的营销策划报告，格式如下：

```markdown
# 营销策划方案：<brief 标题>

## 一、市场洞察（调研员）
...

## 二、竞争分析（分析师）
...

## 三、执行策略（策略师）
...

## 四、综合建议
...
```

### Phase 4：清理团队

```bash
clawteam team shutdown jw-marketing
```

## 注意事项

- **inbox bug 规避**：如果某个 worker 完成后没有发 inbox 消息，直接检查工作目录的 output 文件
- **超时处理**：如果 10 分钟内未完成，读取已完成部分，说明哪部分未完成
- **并行优势**：三个 worker 同时执行，预计总时间 3-5 分钟（vs 单 Hermes 顺序执行 8-12 分钟）

## ClawTeam CLI 速查

```bash
clawteam team list                          # 查看所有团队
clawteam task list <team>                   # 查看团队任务状态
clawteam task list <team> --status pending  # 过滤状态
clawteam inbox peek <team> <agent>          # 查看 agent 收件箱
clawteam board show <team>                  # 终端看板
```
