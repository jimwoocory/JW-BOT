# OpenClaw Briefing - 干净业务输出插件

## 定位

这是新的业务前台插件骨架，目标是把：

- `Harness / workflow / task / replay`
- `AstrBot 前台业务输出`

彻底分层。

它和旧 `oc2_*` 命令不同，默认遵循两条规则：

1. 不暴露系统内部状态、任务日志、搜索焦点。
2. 没有足够可靠的实时结果时，明确返回“今天没有可交付信息”。

## 命令

- `/brief_help`
- `/brief_request <需求>`
- `/brief_daily <主题>`

## 当前状态

这是插件层重构的第一版骨架，用于验证新的业务输出 contract。
