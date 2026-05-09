# Hermes Agent 使用说明

## 📦 安装位置

- **项目目录**: `/Users/dianchi/DC-Agent/hermes-agent-temp`
- **配置目录**: `/Users/dianchi/DC-Agent/hermes-config`
- **虚拟环境**: `/Users/dianchi/DC-Agent/hermes-agent-temp/venv`
- **版本**: v0.8.0 (Python 3.11.15)

## 🚀 快速启动

### 方式 1：使用启动脚本（推荐）
```bash
cd /Users/dianchi/DC-Agent
./hermes-start.sh
```

### 方式 2：直接运行
```bash
cd /Users/dianchi/DC-Agent/hermes-agent-temp
./venv/bin/python -m hermes_cli.main
```

## ⚙️ 配置说明

### 1. 配置 API 密钥
首次使用需要配置 API 密钥：

```bash
./hermes-start.sh setup
```

或手动编辑配置文件：
```bash
# 编辑配置
vim /Users/dianchi/DC-Agent/hermes-config/.env
```

### 2. 支持的模型提供商
Hermes 支持多种模型提供商：
- **Nous Portal** (推荐)
- **OpenRouter** (200+ 模型)
- **OpenAI** (GPT-4, GPT-4o 等)
- **Anthropic** (Claude 系列)
- **z.ai/GLM**
- **Kimi/Moonshot**
- **MiniMax**
- 任何兼容 OpenAI API 的端点

### 3. 选择模型
```bash
./hermes-start.sh model
```

## 🛠️ 常用命令

### 基础命令
```bash
./hermes-start.sh              # 启动交互式对话
./hermes-start.sh chat         # 开始聊天
./hermes-start.sh model        # 选择/切换模型
./hermes-start.sh setup        # 配置向导
./hermes-start.sh status       # 查看状态
./hermes-start.sh --help       # 查看所有命令
```

### 技能管理
```bash
./hermes-start.sh skills       # 浏览和管理技能
./hermes-start.sh skills list  # 列出所有可用技能
```

### 会话管理
```bash
./hermes-start.sh sessions list     # 查看历史会话
./hermes-start.sh sessions export   # 导出会话
```

### 工具配置
```bash
./hermes-start.sh tools      # 配置启用的工具
```

### 查看日志
```bash
./hermes-start.sh logs       # 查看日志
```

## 📝 使用场景

### 1. 代码开发协助
```
/new  # 开始新对话
我需要创建一个用户权限管理模块，使用 Python 和 FastAPI
```

### 2. Debug 协助
```
帮我分析这个错误：[粘贴错误信息]
```

### 3. 代码审查
```
请审查这段代码的安全性和性能：[粘贴代码]
```

### 4. 技术方案设计
```
我需要设计一个高并发的消息队列系统，请给出技术方案
```

## 🔧 高级功能

### 使用技能系统
Hermes 会自动从您的使用中学习并创建技能：
```bash
# 查看所有技能
./hermes-start.sh skills

# 使用特定技能
/<技能名称>
```

### 多会话管理
```bash
# 创建新会话
/new

# 切换会话
/sessions switch <会话名>

# 压缩上下文
/compress
```

### MCP 集成
```bash
# 查看 MCP 服务器
./hermes-start.sh mcp list

# 添加 MCP 服务器
./hermes-start.sh mcp add <服务器>
```

## 💡 使用技巧

1. **善用 `/new` 命令**：开始全新话题时使用，避免上下文污染
2. **使用 `/compress`**：长对话后压缩上下文，节省 token
3. **技能复用**：成功的解决方案会被保存为技能，下次自动复用
4. **跨会话记忆**：Hermes 会记住您的偏好和项目结构
5. **中断与恢复**：可以随时 Ctrl+C 中断当前任务

## 🔍 故障排查

### 查看状态
```bash
./hermes-start.sh doctor
```

### 查看版本
```bash
./hermes-start.sh version
```

### 更新 Hermes
```bash
./hermes-start.sh update
```

## 📚 更多资源

- **官方文档**: https://hermes-agent.nousresearch.com/docs
- **GitHub**: https://github.com/NousResearch/hermes-agent
- **技能中心**: https://agentskills.io

## ⚠️ 注意事项

1. **Python 版本**: 需要 Python 3.11+
2. **API 密钥**: 使用前必须配置至少一个模型提供商的 API 密钥
3. **网络要求**: 需要能够访问模型提供商的 API
4. **磁盘空间**: 完整安装约需要 2-3GB 空间

---

**开始使用**：运行 `./hermes-start.sh` 开始您的第一个对话！
