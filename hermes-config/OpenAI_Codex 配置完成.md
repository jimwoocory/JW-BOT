# OpenAI Codex OAuth 配置完成 ✅

## 📋 配置摘要

已成功将 **OpenClaw 的 OpenAI Codex OAuth 凭证** 迁移到 Hermes Agent！

### 配置详情：

- **提供商**: OpenAI Codex (官方 OAuth)
- **认证方式**: OAuth 2.0 Device Flow
- **账户**: jimwoo.cory@gmail.com
- **默认模型**: `openai-codex/gpt-5.4`
- **认证文件**: `/Users/dianchi/JW-Bot/hermes-config/auth.json`
- **状态**: ✅ 已登录并可用

## 🎯 可用的 GPT 模型

通过 OpenAI Codex，您可以使用以下模型：

| 模型 | 描述 | 适用场景 |
|------|------|----------|
| **gpt-5.4** | 最新版本，最强性能 | 复杂编程、架构设计 |
| **gpt-5** | GPT-5 标准版 | 日常开发任务 |
| **gpt-5-mini** | 轻量快速版 | 简单任务、快速响应 |
| **gpt-4.1** | 经典版本 | 兼容性需求 |
| **gpt-4o** | 多模态模型 | 图像理解任务 |
| **o3** | 推理专用 | 数学、逻辑推理 |
| **o4-mini** | 轻量推理版 | 快速推理任务 |

## 🚀 开始使用

### 1. 启动 Hermes
```bash
cd /Users/dianchi/JW-Bot
./hermes-start.sh
```

### 2. 查看可用模型
```bash
./hermes-start.sh model
```

### 3. 切换模型（可选）
```bash
./hermes-start.sh model
# 然后选择想要的模型，例如 gpt-5.4
```

## 💡 使用示例

### 代码开发
```
/new
我需要创建一个 FastAPI 用户认证模块，包含 JWT token 生成和验证
```

### Debug 协助
```
帮我分析这个 Python 错误：
Traceback (most recent call last):
  File "main.py", line 42, in <module>
    result = process_data(input)
  File "utils.py", line 15, in process_data
    return json.loads(data)
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

### 代码审查
```
请审查这段代码的安全性和性能：
[粘贴您的代码]
```

## 🔧 高级配置

### 修改默认模型
编辑配置文件：
```bash
vim /Users/dianchi/JW-Bot/hermes-config/config.yaml
```

修改：
```yaml
model:
  provider: "openai-codex"
  default: "openai-codex/gpt-5"  # 改为您想要的模型
```

### 查看使用情况
```bash
./hermes-start.sh insights
```

### 查看认证状态
```bash
./hermes-start.sh status
```

## 🔐 认证管理

### 刷新凭证
Hermes 会自动使用 refresh token 刷新访问令牌，无需手动操作。

### 重新认证
如果需要重新认证：
```bash
./hermes-start.sh auth --provider openai-codex
```

### 查看认证详情
```bash
cat /Users/dianchi/JW-Bot/hermes-config/auth.json
```

## ⚠️ 注意事项

1. **Plus 账户要求**: OpenAI Codex 需要 ChatGPT Plus 订阅
2. **使用限制**: 遵循 OpenAI 的速率限制和使用政策
3. **凭证安全**: 
   - 认证文件权限已设置为 600（仅所有者可读写）
   - 不要将 `auth.json` 提交到版本控制
4. **自动刷新**: 凭证快过期时会自动刷新

## 🔗 相关链接

- [OpenAI Codex 文档](https://platform.openai.com/docs)
- [Hermes Agent 文档](https://hermes-agent.nousresearch.com/docs)
- [模型定价](https://openai.com/api/pricing/)

## 📊 与 OpenClaw 的对比

| 特性 | OpenClaw | Hermes Agent |
|------|----------|--------------|
| OAuth 认证 | ✓ | ✓ (已迁移) |
| 技能系统 | ✓ | ✓ (更强大) |
| 记忆系统 | ✓ | ✓ (多层级) |
| 终端后端 | ✓ | ✓ (更多选项) |
| 消息平台 | 有限 | 丰富 |
| 学习循环 | 基础 | 高级 |

## ✨ 下一步

现在您可以开始使用 Hermes Agent 作为开发助手了！

```bash
# 开始聊天
./hermes-start.sh

# 或者查看帮助
./hermes-start.sh --help
```

---

**配置完成时间**: 2026-04-11  
**配置账户**: jimwoo.cory@gmail.com  
**默认模型**: openai-codex/gpt-5.4

🎉 祝您使用愉快！
