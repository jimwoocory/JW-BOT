# Unit Test Report — 2026-04-18

## 执行命令
```bash
cd /Users/dianchi/JW-Bot
uv run pytest tests/unit/ -x -q
```

## 结果摘要
- **总计：434 passed / 0 failed / 0 error**
- **所有测试均通过！**
- 耗时：8.63s

## 警告信息
仅 3 个 DeprecationWarning（来自 `<frozen importlib._bootstrap>`，与 SwigPyPacked/SwigPyObject/swigvarlink 相关），不影响测试通过。

## 每条失败的根因（一句话）
无失败测试。

## 建议（给 Claude 看）
- 测试全部通过，memory_promoter 接入后未引入回归问题。
- Task C（补测试 stub）仍可进行，以增加未覆盖分支的测试覆盖率。

---

## Channel Directory 健康检查

### 文件信息
- 路径：`hermes-config/channel_directory.json`
- 更新时间：`2026-04-18T01:49:29.331304`

### 结构分析
```json
{
  "updated_at": "...",
  "platforms": {
    "telegram": [],
    "discord": [],
    ... (16 个平台，全部为空数组)
  }
}
```

| 检查项 | 结果 | 备注 |
|--------|------|------|
| JSON 格式合法 | ✅ | 可正常解析 |
| 包含 `updated_at` 字段 | ✅ | 有更新时间戳 |
| 包含 `platforms` 字段 | ✅ | 定义了 16 个平台 |
| 每个平台 entry 为数组 | ✅ | 格式一致 |

### ⚠️ 需要修复

1. **所有平台 channel 列表为空**：16 个平台（telegram, discord, whatsapp, slack, signal, mattermost, matrix, homeassistant, email, sms, dingtalk, feishu, wecom, wecom_callback, weixin, bluebubbles, qqbot）的 channel 数组全部为 `[]`，没有配置任何实际频道。

2. **缺少 `webhook` 平台**：`config.yaml` 中实际启用的平台是 `webhook`（端口 8644，包含 `astrbot_qq` 路由），但 `channel_directory.json` 中**没有 `webhook` 这个 key**。

3. **与 config.yaml 不匹配**：
   - `config.yaml` 的 `platforms.webhook.routes` 中定义了 `astrbot_qq` 路由
   - `channel_directory.json` 中完全没有对应条目
   - Hermes 可能无法正确路由来自 AstrBot 的 QQ 消息

### ❓ 待确认
- `channel_directory.json` 是否应该由 Hermes CLI 自动生成/同步？
- 是否需要手动添加 `webhook` 平台及 `astrbot_qq` channel 条目？
- 空的 channel 列表是正常状态（等待用户配置），还是配置文件丢失？
