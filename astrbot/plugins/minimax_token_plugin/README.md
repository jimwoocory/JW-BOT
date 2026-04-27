# MiniMax Token 监控插件

这是一个用于监控 MiniMax API Token 余额的 AstrBot 插件，支持定时检查和余额提醒功能。

**注意**：本插件使用第三方中转服务商 (`https://minimax.a7m.com.cn/`) 的 API 接口。

## 功能特性

- ✅ 定时自动检查 Token 余额（默认每 6 小时）
- ✅ 余额不足时自动告警
- ✅ 手动查询余额
- ✅ 自定义提醒阈值
- ✅ 显示 API Key 后六位（lVJnPr）
- ✅ 测试 API 连接

## 安装方法

1. 将 `minimax_token_plugin` 文件夹放入 AstrBot 的 `plugins` 目录
2. 重启 AstrBot

## 配置方法

编辑 `config.json` 文件：

```json
{
  "api_key": "你的 MiniMax API Key",
  "api_key_suffix": "lVJnPr",
  "credit_threshold": 1000,
  "weekly_limit": 5000,
  "check_interval_hours": 6,
  "api_base_url": "https://minimax.a7m.com.cn",
  "balance_endpoint": "/v1/api/balance"
}
```

### 配置项说明

- `api_key`: 你的 MiniMax API Key（必填）
- `api_key_suffix`: API Key 后六位，用于提醒时显示（默认：lVJnPr）
- `credit_threshold`: 余额提醒阈值，低于此值会告警（默认：1000）
- `weekly_limit`: 周上限额度（默认：5000）
- `check_interval_hours`: 检查间隔时间（小时）（默认：6）
- `api_base_url`: 中转服务商 API 地址（默认：https://minimax.a7m.com.cn）
- `balance_endpoint`: 余额查询 API 端点（默认：/v1/api/balance，如果不对请咨询服务商）

## 使用方法

### 1. 查询余额
```
/minimax 余额
```
显示周额度、剩余余额、已使用量和百分比。

### 2. 设置提醒阈值
```
/设置 minimax 提醒 500
```

### 3. 设置周额度
```
/设置 minimax 周额度 5000
```

### 4. 测试连接
```
/minimax 测试
```

## 定时检查

插件会自动注册定时任务，每 6 小时（可配置）检查一次余额：
- 余额充足时：记录 INFO 级别日志
- 余额不足时：记录 WARNING 级别日志并告警

## 注意事项

1. **API Key 安全**：请妥善保管你的 API Key，不要泄露
2. **中转服务商**：本插件使用第三方中转服务商，非 MiniMax 官方 API
3. **网络要求**：确保服务器可以访问 `https://minimax.a7m.com.cn`
4. **高峰期提醒**：15:00~17:30 为官方高峰期，此区间双倍计费且错误率提升

## API 接口

插件使用中转服务商的 API 查询余额：
- Endpoint: `https://minimax.a7m.com.cn/v1/api/balance`
- 方法：GET
- 认证：Bearer Token

## 故障排除

### 查询失败
1. 检查 API Key 是否正确
2. 检查网络连接
3. 确认已购买 Token Plan

### 插件未加载
1. 检查是否放在正确的目录
2. 查看 AstrBot 日志是否有错误信息
3. 确认 `config.json` 格式正确

## 开发者

如有问题或建议，欢迎反馈。
