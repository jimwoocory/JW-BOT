# 当前开发优先级

_最后更新：2026-04-16_

## 近期已完成的工作

- ✅ dreamina_plugin 修复：`subprocess.run` 改为 `asyncio.to_thread`，解决 bot 卡死问题
- ✅ dreamina_plugin 修复：`gen_status: fail` 不再误报成功
- ✅ dreamina_plugin 新增：ExceedConcurrencyLimit 自动重试
- ✅ dreamina_plugin 新增：自然语言触发（regex handler + `event.stop_event()`）
- ✅ 三个频道人格重写：去除 OpenClaw 相关内容，改写为现有系统能力
- ✅ Hermes SOUL 重写：从通用助手 → JW-Bot 专属开发 agent
- ✅ 主 LLM 从 MiniMax-M2.7-highspeed 切换至 gpt-5.4-nano（MiniMax 不支持 function calling）

## 待开发项（按优先级）

### P0 — Harness Phase 1（核心任务）
参考 `/Users/dianchi/DC-Agent/harness-engineering-phase1-plan.md`
1. `orchestrator.py` — 任务执行编排器
2. `tool_interceptor.py` — 工具调用拦截与验证
3. `workflow_engine.py` — 工作流执行引擎
4. `quality_checkpoints.py` — 执行质量检查
5. 集成到 `InternalAgentSubStage`

### P1 — dreamina_plugin 改进
- `last_image_path` 现在是内存变量，bot 重启后丢失，考虑持久化到数据库
- 图片转视频功能（`image2video` CLI 命令）需要验证 dreamina CLI 是否支持

### P2 — AstrBot 系统观察
- 定期读取 astrbot.log，识别员工频繁遇到的问题
- 将观察结果记录到 `/Users/dianchi/DC-Agent/hermes-workspace/observations/`

## 观察到的问题模式

（此节由 Hermes 自行维护，记录从 astrbot.log 和员工反馈中观察到的规律）
