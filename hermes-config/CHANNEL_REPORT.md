# Channel Directory Validation Report - 2026-04-18

## 文件信息

- 文件路径：`hermes-config/channel_directory.json`
- 上次修改：`2026-04-18 02:14:31 +0800`
- 大小：`399 bytes`

## 结构校验结果

- 顶层结构包含：
  - `updated_at`
  - `platforms`
- `platforms` 当前包含 17 个平台 bucket：
  - `telegram`
  - `discord`
  - `whatsapp`
  - `slack`
  - `signal`
  - `mattermost`
  - `matrix`
  - `homeassistant`
  - `email`
  - `sms`
  - `dingtalk`
  - `feishu`
  - `wecom`
  - `wecom_callback`
  - `weixin`
  - `bluebubbles`
  - `qqbot`
- 所有 platform bucket 当前都是空数组。

### 必填字段检查

| channel_id | platform_id | channel_name | webhook_url | 缺失字段 | 状态 |
|------------|-------------|--------------|-------------|----------|------|
| `(no channel entries)` | - | - | - | - | N/A |

### 引用完整性检查

| 问题类型 | 数量 | 具体项 |
|---------|------|--------|
| 悬空 `platform_id` | 0 | 无。当前没有 channel entry。 |
| 无效 webhook URL | 0 | 无。当前没有 `webhook_url` 字段需要校验。 |
| 重复 `channel_id` | 0 | 无。当前没有 channel entry。 |
| 非数组 platform bucket | 0 | 所有平台值都是数组。 |

### 总体状态

- ✅ 结构合法，但当前是“空目录”状态
- ⚠️ 无任何已登记 channel，因此本次只能验证 schema 轮廓，无法验证单条路由配置质量

## 发现的问题

- 无结构性错误。
- 当前 `channel_directory.json` 还没有任何 channel entry，因此不存在缺字段、重复 ID、悬空 `platform_id` 或非法 webhook URL 的实例。
- `hermes-config/config.yaml` 中也没有额外定义 channel schema；它更多提供模型、代理、终端、平台行为等全局配置，因此本次必填字段判断只能依据 `channel_directory.json` 现有设计进行保守校验。

## 建议

1. 当后续开始登记真实 channel 时，建议把单条 entry 至少统一到这组基础字段：`id`、`platform_id`、`channel_name`，并在需要 webhook 时补 `webhook_url`。
2. 如果 `channel_directory.json` 将长期作为路由注册表，最好补一份明确 schema 文档，避免不同写入方使用不同字段名。
3. 在有真实 entry 之前，这个文件可视为“初始化完成但尚未启用”的空目录索引。
