# Hermes Workspace — JW-Bot

这是 Hermes Agent 的专属工作目录。

## 目录结构

- `observations/` — 从 astrbot.log 和员工反馈中整理的问题观察记录
- `tasks/` — 当前和历史任务的执行记录
- `patches/` — 提交到 JW-Bot 代码库的改动草稿
- `reports/` — 阶段性总结和质量报告

## 工作方式

Hermes 通过 hermes_bridge 接收来自「癫池-测试」频道的消息。
观察到问题后，在 observations/ 记录，在 tasks/ 立项，在 patches/ 起草改动，
验证通过后写入 JW-Bot 代码库并重启 AstrBot。

## 关键路径

- AstrBot 代码：`/Users/dianchi/JW-Bot/`
- 运行日志：`/Users/dianchi/JW-Bot/astrbot.log`
- Harness 核心：`/Users/dianchi/JW-Bot/astrbot/core/harness/`
- Hermes 记忆：`/Users/dianchi/JW-Bot/hermes-config/memories/`
