
# OpenClaw Core v2 - AstrBot 插件

## 📦 插件信息

- **插件名称**: `openclaw_core_v2`
- **版本**: 2.0.0
- **作者**: OpenClaw Team
- **功能**: 面向运营与推广团队的 JW-Claw Harness 作战台入口（命令以 `/oc2_` 开头）

## 📁 文件结构

```
openclaw_core_v2/
├── __init__.py
├── main.py              # 主入口 + 所有命令
├── config.json          # 配置文件
├── README.md            # 说明文档
└── core/                # 核心模块（业务逻辑）
    ├── __init__.py
    ├── feature_flags.py # 功能标志
    ├── permissions.py   # 权限系统
    ├── tasks.py         # 任务系统
    └── memory.py        # 记忆系统
```

当前插件入口采用：

- `main.py`
  AstrBot 薄壳入口与命令汇总
- `core/`
  Legacy 运营能力与兼容管理
- `jw_claw/`
  Harness、Bridge、任务、审查、记忆、项目上下文主链

## 🚀 使用方法

重启 AstrBot 即可加载插件！

## 💬 命令列表（注意：以 /oc2_ 开头）

### 核心命令

| 命令 | 说明 |
|------|------|
| `/oc2_core` | 显示所有 Openclaw Core v2 命令帮助 |
| `/oc2_core_about` | 关于 Openclaw Core v2 的详细介绍 |
| `/oc2_demo` | 快速演示功能 |
| `/oc2_status` | 查看 JW-Claw Harness 状态 |
| `/oc2_route_debug &lt;text&gt;` | 调试消息路由结果 |

### 功能标志系统

| 命令 | 说明 |
|------|------|
| `/oc2_flags` | 查看所有功能标志状态 |
| `/oc2_flags_enable &lt;flag&gt;` | 启用功能 |
| `/oc2_flags_disable &lt;flag&gt;` | 禁用功能 |

### 权限系统

| 命令 | 说明 |
|------|------|
| `/oc2_perms` | 查看当前权限规则 |
| `/oc2_perms_add &lt;pattern&gt; &lt;allow/deny&gt;` | 添加权限规则 |
| `/oc2_perms_mode &lt;mode&gt;` | 设置权限模式 |

### 任务系统

| 命令 | 说明 |
|------|------|
| `/oc2_tasks` | 查看任务列表、分类、优先关注与回退提示 |
| `/oc2_task_create &lt;command&gt;` | 创建 Shell 任务 |

### 记忆系统

| 命令 | 说明 |
|------|------|
| `/oc2_memory` | 查看 JW-Claw 持久记忆与 Legacy 记忆摘要 |
| `/oc2_memory_add &lt;content&gt;` | 添加记忆（当前为兼容双写） |
| `/oc2_memory_search &lt;query&gt;` | 搜索记忆并查看跟进提示 |
| `/oc2_project_context &lt;query&gt;` | 查看客户项目上下文面板 |

## 🧭 推荐使用顺序

当前建议团队按这个顺序使用：

1. `/oc2_tasks`
   先看当前优先关注、技术回退和高价值客户洞察
2. `/oc2_project_context <query>`
   再看客户项目上下文、平台焦点、搜索焦点和下一步动作
3. `/oc2_memory_search <query>`
   最后深挖历史记忆、持久线索和跟进提示

## 🔀 当前迁移状态

`openclaw_core_v2` 现在不是单纯“另一套 core 命令”，而是：

- 新的 Harness 运营视图入口
- 旧版任务/记忆管理的兼容展示层
- `marketing_tools`、`marketing_opencli` 等已接入新主链后的观察入口

因此你在这里会同时看到：

- `JW-Claw` 任务与记忆
- `Legacy` 任务与记忆
- Harness 状态与调试能力

这是当前并行迁移策略的一部分，不是重复设计。

## 🎯 业务场景

当前高频使用场景包括：

- 柳州五菱项目跟进
- 柳汽东风传播复盘
- 新能源汽车行业热点追踪
- 小红书 / 抖音 / 微博 / 知乎 平台线索整理

这些场景都可以通过 `/oc2_project_context` 和 `/oc2_memory_search` 直接查看。

## 🎯 设计说明

- **v1 插件**（`/oc_` 开头）: 单文件简化版，稳定可靠
- **v2 插件**（`/oc2_` 开头）: 以 `main.py` 作为 AstrBot 薄壳入口，核心逻辑收敛在 `core/` 与 `jw_claw/`

两个插件可以同时使用！
