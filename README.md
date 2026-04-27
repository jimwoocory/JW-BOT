# JW-Bot — 企业内部 AI 办公系统

> 基于 **AstrBot + Hermes Agent** 双系统协作架构的智能办公助手平台  
> 支持 QQ 官方机器人 · 飞书机器人 · Web 聊天界面

---

## 系统概览

JW-Bot 是专为企业内部办公场景设计的 AI 助手系统，员工通过 QQ 或飞书与机器人对话，即可完成营销策划、项目跟进、内容交付、审批发起等工作任务。

系统采用**前台 + 后台**双引擎架构：

```
员工（QQ / 飞书 / WebChat）
         ↓
    ┌────────────────────────────────┐
    │         AstrBot 前台           │
    │  意图路由 → 任务管理 → AI 回复  │
    └──────────────┬─────────────────┘
                   │ 复杂任务升级
    ┌──────────────▼─────────────────┐
    │         Hermes 后台            │
    │  联网搜索 · 多步执行 · 深度分析  │
    └────────────────────────────────┘
```

| 系统 | 角色 | 核心能力 |
|------|------|----------|
| **AstrBot** | 前台接待 | QQ/飞书适配、意图分类、任务管理、多用户会话、即时回复 |
| **Hermes Agent** | 后台执行 | 联网搜索、多步骤工具链、自主深度分析 |

---

## 核心功能

### 🧭 智能意图路由（Router）
自动识别员工消息意图，分流至最合适的处理路径：
- **工作任务** → Harness 任务系统创建档案
- **技能调用** → 对应插件（图片生成、PPT 制作等）
- **普通对话** → AI 直接回复

支持关键词规则匹配 + LLM 二次判断双重保障。

### 📋 Harness 马绳任务系统
企业级任务全生命周期管理：
- 任务创建、状态追踪、历史记录
- 短期上下文记忆 + 长期任务记忆积累
- **满意度驱动升级**：员工不满意时自动派发 Hermes 深度执行（二期）

### 🤝 新员工引导（Onboarding）
首次使用自动触发 ABC 角色选择，绑定专属 AI 人格：
- **A — 推广运营助手**（`Biz_Assistant_Claw`）
- **B — 项目跟进助手**（`Enterprise_Ops_Kernel`）
- **C — 技术运维助手**（`DevOps_Console`）

### 🔗 AstrBot ↔ Hermes 双向桥接
- `hermes_bridge` 插件实现任务派发与结果回传
- Hermes 完成深度任务后，结果自动推送回 QQ/飞书用户
- 全链路任务闭环

### 🎨 即梦 AI 创意工具
- 文生图、文生视频、图片转视频
- 余额查询与提醒

---

## 系统架构

```
员工消息
    ↓
RouterStage        意图分类（规则匹配 + LLM fallback）
    ├─ task      → Harness.create_task() → [AstrBot LLM / Hermes 执行]
    ├─ skill     → Star Handler（dreamina / builtin_commands 等）
    └─ conversation → LLM Agent 直接回复
                           ↓
ProcessStage       插件处理 / LLM 生成响应
                           ↓
RespondStage       推送回平台（QQ / 飞书 / WebChat）
```

### 数据存储

| 数据库文件 | 内容 |
|-----------|------|
| `data/data_v4.db` | 会话历史、Persona、session 配置 |
| `data/lossless_context.db` | 无损压缩上下文 |
| `data/harness.db` | Harness 任务记录 |
| `data/harness_memory.db` | 任务记忆积累 |
| `data/knowledge_base/kb.db` | 知识库元数据 |
| `data/hermes_sessions.db` | Hermes 会话映射 |

---

## 插件列表

| 插件 | 路径 | 功能 |
|------|------|------|
| `onboarding_guide` | `data/plugins/onboarding_guide/` | 新员工 ABC 引导 + 人格绑定 |
| `hermes_bridge` | `data/plugins/hermes_bridge/` | AstrBot ↔ Hermes 双向桥接 |
| `dreamina_plugin` | `data/plugins/dreamina_plugin/` | 即梦 AI 图片/视频生成 |
| `builtin_commands` | `astrbot/builtin_stars/builtin_commands/` | /task 任务系列命令 |
| `session_controller` | `astrbot/builtin_stars/session_controller/` | 会话 LLM 开关控制 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前台平台 | [AstrBot](https://github.com/Soulter/AstrBot) v4.22+ |
| 后台执行 | [Hermes Agent](https://github.com/NousResearch/hermes-agent) |
| 消息平台 | QQ 官方机器人 API · 飞书开放平台 |
| LLM 模型 | MiniMax M2.7 / 可配置其他提供商 |
| 任务存储 | SQLite（harness.db / data_v4.db） |
| 服务通信 | aiohttp Webhook（8644/8645 端口） |
| 运行环境 | macOS（Mac mini）· Python 3.11+ |

---

## 部署说明

### 环境要求
- Python 3.11+
- AstrBot v4.22+
- Hermes Agent（独立部署）
- Mac mini 或同等服务器（长期运行）

### 快速启动

```bash
# 启动 AstrBot
bash start-astrbot.sh

# 启动 Hermes Gateway（后台服务）
hermes gateway start

# 查看实时日志
tail -f logs/launchd.out.log
```

### 网络配置说明

QQ 和飞书 API 域名需在路由器配置直连规则，避免代理导致连接异常：
```
DOMAIN-SUFFIX,sgroup.qq.com,DIRECT
DOMAIN-SUFFIX,nt.qq.com.cn,DIRECT
DOMAIN-SUFFIX,open.feishu.cn,DIRECT
```

---

## 开发文档

详细技术文档位于 `doc/` 目录：

| 文档 | 说明 |
|------|------|
| [系统架构总览](doc/系统架构总览.md) | 整体架构、数据流、存储结构 |
| [Router 意图路由系统](doc/Router意图路由系统.md) | 分类规则、配置方式、扩展方法 |
| [Harness 马绳任务系统](doc/Harness马绳任务系统.md) | 任务生命周期、闭环机制、记忆提升 |
| [HermesBridge 集成说明](doc/HermesBridge集成说明.md) | 双向桥接、SessionRouter、回传机制 |
| [Hermes 定位与双系统架构](doc/Hermes定位与双系统架构设计.md) | 双系统协作逻辑、满意度升级机制 |
| [方案 C 协作架构](doc/方案C-AstrBot与Hermes协作架构.md) | AstrBot + Hermes 任务派发协议 |
| [新员工引导系统](doc/新员工引导系统.md) | ABC 引导插件、角色映射 |
| [运维排障记录](doc/运维排障记录.md) | 已修复问题记录、通用排障命令 |

---

## 项目状态

**当前阶段：一期上线 · 二期开发中**

| 功能模块 | 状态 |
|----------|------|
| QQ / 飞书 机器人接入 | ✅ 已上线 |
| 智能意图路由（Router） | ✅ 已上线 |
| Harness 任务系统 | ✅ 已上线 |
| 新员工引导（ABC 人格绑定） | ✅ 已上线 |
| AstrBot ↔ Hermes 桥接 | ✅ 已上线 |
| 即梦 AI 图片/视频生成 | ✅ 已上线 |
| 知识库接入任务链路 | ⏳ 二期开发 |
| Harness 满意度检测 → Hermes 升级 | ⏳ 二期核心 |
| 短期/长期记忆激活 | ⏳ 二期开发 |
| 多任务并发分流架构 | 📋 规划中 |

---

*内部系统 · 非公开发布*
