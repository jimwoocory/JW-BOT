# JW-BOT

<div align="center">

**基于 AstrBot 和 Hermes Agent 的多功能 AI 机器人框架**

[![License](https://img.shields.io/github/license/jimwoocory/JW-BOT)](https://github.com/jimwoocory/JW-BOT/blob/master/LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![AstrBot](https://img.shields.io/badge/AstrBot-4.22.3-green.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Hermes](https://img.shields.io/badge/Hermes-Agent-orange.svg)](https://hermes-agent.nousresearch.com/)

[English](README_en.md) | [简体中文](README.md)

</div>

---

## 📖 简介

JW-BOT 是一个功能强大的多平台 AI 机器人框架，集成了 **AstrBot** 和 **Hermes Agent** 两大核心系统。它支持多个即时通讯平台，提供持久化记忆、定时任务、技能系统等高级功能，适用于构建智能客服、自动化助手、内容创作工具等多种应用场景。

### ✨ 主要特性

- **多平台支持** - 支持 QQ、微信、Telegram、Discord、Slack 等 10+ 个通讯平台
- **持久化记忆** - 跨会话记忆能力，自动学习用户偏好和项目规范
- **定时任务系统** - 支持 cron 表达式，可在离线时自动执行任务
- **技能系统** - 自动编写和保存可复用技能，持续进化
- **多模型支持** - OpenAI、Anthropic、Google、DeepSeek 等主流 LLM
- **Web 管理界面** - 暗色主题，三栏布局，实时对话管理
- **自主增强** - 可根据经验自动改进技能和行为模式

## 🚀 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+ (用于 WebUI)
- pnpm (用于 WebUI 依赖管理)

### 安装

#### 1. 克隆项目

```bash
git clone https://github.com/jimwoocory/JW-BOT.git
cd JW-Bot
```

#### 2. 安装核心依赖

```bash
# 使用 uv 管理依赖（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

#### 3. 启动核心服务

```bash
uv run main.py
```

默认 API 服务运行在 `http://localhost:6185`

#### 4. 启动 WebUI（可选）

```bash
cd hermes-webui
pnpm install  # 首次安装
pnpm dev
```

WebUI 运行在 `http://localhost:3000`

#### 5. 一键启动所有服务

```bash
./start-all.sh
```

## 📁 项目结构

```
JW-BOT/
├── astrbot/                      # AstrBot 核心框架
│   ├── api/                      # API 接口定义
│   ├── core/                     # 核心功能实现
│   │   ├── agent/                # Agent 运行逻辑
│   │   ├── platform/             # 平台适配器
│   │   ├── provider/             # LLM 提供商管理
│   │   ├── star/                 # 插件系统
│   │   └── harness/              # 任务编排引擎
│   ├── dashboard/                # 管理后台
│   └── plugins/                  # 内置插件
├── hermes-agent-temp/            # Hermes Agent 核心
├── hermes-config/                # Hermes 配置文件
├── hermes-webui/                 # Hermes Web 界面
├── dashboard/                    # 前端管理界面 (Vue3)
├── docs/                         # 文档
├── tests/                        # 测试用例
└── scripts/                      # 工具脚本
```

## 🛠️ 核心功能

### 1. AstrBot 功能

- **多平台消息适配** - 统一的消息抽象层，支持主流 IM 平台
- **插件系统** - 灵活的 Star 插件机制，支持热加载
- **知识库** - 基于 FAISS 的向量数据库，支持 RAG
- **MCP 支持** - Model Context Protocol 集成
- **Agent 编排** - 多 Agent 协作和任务分发

### 2. Hermes Agent 功能

- **持久化记忆** - USER.md 和 MEMORY.md 跨会话记忆
- **技能系统** - 自动编写、保存、改进技能
- **定时任务** - 自托管 cron 任务，离线执行
- **多配置文件** - Profile 系统，快速切换配置
- **10+ 通讯平台** - Telegram、Discord、Slack、Signal 等

### 3. WebUI 功能

- **三栏布局** - 会话列表、对话区域、工作区文件浏览
- **实时流式响应** - SSE 实时 token 输出
- **会话管理** - 创建、搜索、归档、导出会话
- **文件工作区** - 在线编辑、预览、管理文件
- **多主题支持** - 6 种内置主题，支持自定义
- **移动端优化** - 响应式设计，支持手机访问

### 4. Harness Engineering（任务编排工程）

- **任务编排器** - Harness Orchestrator 负责任务执行的协调与管理
- **工具调用拦截** - 在工具执行前后进行验证和记录，防止偏离任务目标
- **工作流引擎** - 支持多种工作流模板（营销策划、代码开发等），自动执行步骤验证
- **质量检查点** - 在关键节点自动检查执行质量（任务对齐、工具使用、结果完整性）
- **自动审查机制** - 根据执行结果自动判断是否需要人工审查
- **执行轨迹记录** - 完整的任务执行日志，支持追溯和审计
- **记忆提升系统** - 从任务执行中提取关键信息，自动更新记忆系统

## ⚙️ 配置说明

### 基础配置

配置文件位于 `astrbot/core/config/default.py`

```python
# 示例配置
PLATFORM_QQ = {
    "enabled": True,
    "app_id": "your_app_id",
    "app_secret": "your_app_secret",
}

PROVIDER_OPENAI = {
    "api_key": "sk-xxx",
    "model": "gpt-4",
    "base_url": "https://api.openai.com/v1",
}
```

### Hermes 配置

配置文件位于 `hermes-config/config.yaml`

```yaml
# Hermes 配置示例
llm:
  provider: openai
  model: gpt-4
  api_key: sk-xxx

memory:
  enabled: true
  path: ~/.hermes/memory

cron:
  enabled: true
  timezone: Asia/Shanghai
```

## 📝 使用示例

### 创建自定义插件

```python
# astrbot/plugins/my_plugin/main.py
from astrbot.api.star import Star, register
from astrbot.api.event import AstrMessageEvent

@register("my_plugin")
class MyPlugin(Star):
    async def on_message(self, event: AstrMessageEvent):
        if event.get_message() == "hello":
            await event.send("Hello! I'm your AI assistant.")
```

### 配置定时任务

```bash
# 每 5 分钟执行一次
hermes cron add "*/5 * * * *" "python scripts/check_status.py"
```

### 使用 WebUI 对话

1. 访问 `http://localhost:3000`
2. 创建新会话
3. 在对话框输入消息
4. 查看实时响应和工具调用

## 🔧 开发指南

### 代码规范

```bash
# 格式化代码
ruff format .

# 检查代码
ruff check .
```

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/unit/test_core.py -v
```

### 提交规范

使用 Conventional Commits:

```bash
feat: add new agent for data analysis
fix: resolve bug in provider manager
docs: update API documentation
```

## 📊 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    JW-BOT                           │
├─────────────────────────────────────────────────────┤
│  ┌──────────────┐         ┌──────────────────────┐ │
│  │   AstrBot    │         │   Hermes Agent       │ │
│  │              │         │                      │ │
│  │ - Platform   │         │ - Memory System      │ │
│  │ - Provider   │         │ - Skills System      │ │
│  │ - Star       │         │ - Cron Jobs          │ │
│  │ - Knowledge  │         │ - Profiles           │ │
│  └──────────────┘         └──────────────────────┘ │
│              │                      │               │
│              └──────────┬───────────┘               │
│                         │                           │
│              ┌──────────▼───────────┐               │
│              │   WebUI Dashboard    │               │
│              │                      │               │
│              │ - Chat Interface     │               │
│              │ - Session Manager    │               │
│              │ - File Workspace     │               │
│              └──────────────────────┘               │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
   │   QQ    │     │Telegram │     │ Discord │
   └─────────┘     └─────────┘     └─────────
```

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📄 许可证

本项目采用 AGPL-3.0-or-later 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) - 多平台 LLM 聊天机器人框架
- [Hermes Agent](https://hermes-agent.nousresearch.com/) - 自托管 AI Agent
- 所有贡献者和支持者

## 📞 联系方式

- 项目地址：https://github.com/jimwoocory/JW-BOT
- 问题反馈：https://github.com/jimwoocory/JW-BOT/issues
- 作者：jimwoocory

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star 支持！**

Made with ❤️ by JW-BOT Team

</div>
