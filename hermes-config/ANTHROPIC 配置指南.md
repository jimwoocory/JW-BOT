# Anthropic (Claude) 配置指南

## ✅ 已完成的配置

Hermes 已经配置为使用 **Anthropic 官方 API**，而不是通过 OpenRouter 中转。

### 配置文件修改：

1. **config.yaml** - 已修改：
   ```yaml
   model:
     provider: "anthropic"  # 直接使用 Anthropic API
     default: "anthropic/claude-opus-4.6"
   ```

2. **.env** - 已添加：
   ```bash
   # LLM PROVIDER (Anthropic - Claude)
   ANTHROPIC_API_KEY=
   ```

## 🔑 下一步：获取并配置 API 密钥

### 1. 获取 Anthropic API 密钥

访问 Anthropic 控制台：
```
https://console.anthropic.com/settings/keys
```

步骤：
1. 登录或注册 Anthropic 账户
2. 进入 Settings → API Keys
3. 点击 "Create Key"
4. 复制生成的密钥（格式：`sk-ant-...`）

### 2. 配置 API 密钥

#### 方式 1：直接编辑 .env 文件
```bash
vim /Users/dianchi/DC-Agent/hermes-config/.env
```

找到这一行：
```bash
# ANTHROPIC_API_KEY=
```

修改为（替换为您的实际密钥）：
```bash
ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 方式 2：使用命令行
```bash
cd /Users/dianchi/DC-Agent/hermes-config
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env
```

### 3. 验证配置

运行以下命令测试配置：
```bash
cd /Users/dianchi/DC-Agent
./hermes-start.sh doctor
```

## 📊 可用的 Claude 模型

在 config.yaml 中修改 `model.default` 来切换模型：

```yaml
model:
  default: "anthropic/claude-opus-4.6"     # 最强模型，适合复杂任务
  # default: "anthropic/claude-sonnet-4.6"  # 平衡性能和速度
  # default: "anthropic/claude-haiku-4.5"   # 快速、经济，适合简单任务
```

### 模型对比：

| 模型 | 特点 | 适用场景 | 价格 |
|------|------|----------|------|
| **Claude Opus 4.6** | 最强智能 | 复杂编程、架构设计 | $$$$ |
| **Claude Sonnet 4.6** | 平衡性能 | 日常开发、代码审查 | $$$ |
| **Claude Haiku 4.5** | 快速经济 | 简单任务、快速迭代 | $$ |

## 🚀 开始使用

配置完成后，启动 Hermes：
```bash
cd /Users/dianchi/DC-Agent
./hermes-start.sh
```

## 💡 使用技巧

### 1. 切换模型
```bash
./hermes-start.sh model
# 然后选择想要的 Claude 模型
```

### 2. 查看使用情况
```bash
./hermes-start.sh insights
```

### 3. 查看当前配置
```bash
./hermes-start.sh status
```

## ⚠️ 注意事项

1. **API 费用**：直接使用 Anthropic API 会按使用量计费
   - 查看价格：https://www.anthropic.com/pricing
   - 设置使用限额：https://console.anthropic.com/settings/billing

2. **网络要求**：需要能够访问 `https://api.anthropic.com`

3. **密钥安全**：
   - 不要将 `.env` 文件提交到 Git
   - 定期轮换密钥
   - 使用最小权限原则

## 🔗 相关链接

- Anthropic 控制台：https://console.anthropic.com
- API 文档：https://docs.anthropic.com
- 模型定价：https://www.anthropic.com/pricing
- 使用限制：https://console.anthropic.com/settings/limits

---

**配置完成后，运行 `./hermes-start.sh` 开始使用 Claude！**
