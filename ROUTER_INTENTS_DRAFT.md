# Router Intents - Draft

## 强信号（命令前缀/关键词）

- `/task new` -> harness task creation
- `/task intake marketing_plan ...` -> harness workflow `marketing_plan`
- `/task intake content_delivery ...` -> harness workflow `content_delivery`
- `/task intake project_followup ...` -> harness workflow `project_followup`
- `/task intake approval_request ...` -> harness workflow `approval_request`
- `/task ls` -> list harness tasks in current conversation
- `/task show <task_id>` -> inspect one harness task
- `/task start <task_id>` -> mark task in progress
- `/task review <task_id>` -> move task into review
- `/task done <task_id> [summary]` -> submit workflow result or complete task
- `/task fail <task_id> <reason>` -> mark task failed
- `/task approve <task_id> [note]` -> approve reviewed task
- `/task reject <task_id> <note>` -> reject reviewed task
- `生成图片` / `画一张` / `做一张图` / `制作插画` -> `dreamina_plugin`
- `生成视频` / `做个视频` / `生成动画` / `短片` -> `dreamina_plugin`
- `图片转视频` -> `dreamina_plugin`
- `即梦余额` / `设置余额提醒` / `即梦任务列表` / `查询即梦任务` -> `dreamina_plugin`

## 弱信号（需要 LLM 分类）

- “帮我做本周推广计划” / “给我一个营销方案” -> 更像 `marketing_plan`
- “把这批内容整理成可交付结果” / “今天要交的内容给我列出来” -> 更像 `content_delivery`
- “跟进一下这个项目现在到哪了” / “帮我梳理风险和下一步” -> 更像 `project_followup`
- “这个要不要批准” / “帮我整理一个审批结论” -> 更像 `approval_request`
- “帮我画图” / “来一张海报” / “把这个场景做成图” -> 更像 `dreamina_plugin`
- “把这张图动起来” / “做成动画短片” -> 更像 `dreamina_plugin`

## HarnessWorkflowKind 完整映射

| 关键词 | kind |
|--------|------|
| 营销计划 / 推广计划 / 营销方案 / 渠道规划 / KPI | `marketing_plan` |
| 内容交付 / 交付物 / 截止时间 / 负责人 / 素材交付 | `content_delivery` |
| 项目跟进 / 当前进度 / 风险 / 下一步 / follow-up | `project_followup` |
| 审批 / 批准 / 驳回 / blocking reason / decision | `approval_request` |

## Workflow 结果字段提示

- `marketing_plan` 期望输出：`strategy`, `channels`, `timeline`, `kpis`
- `content_delivery` 期望输出：`deliverables`, `deadline`, `owner`
- `project_followup` 期望输出：`progress`, `risks`, `next_actions`
- `approval_request` 期望输出：`decision`, `owner`, `blocking_reason`

## Hermes Bridge Signals

- 这更像 transport intent，不是用户显式命令。
- 触发来源是 QQ 文本消息：插件会从 `Plain` 组件拼出 `message_text` 后转发。
- 桥接 payload 关键字段：`user_id`, `session_key`, `message`, `message_type`, `platform`, `message_id`, `sender_nickname`
- 桥接请求头关键字段：`X-Webhook-Event=qq_message`, `X-User-ID`, `X-Session-Key`
- 接收端路径：`/hermes_response` 和 `/webhooks/astrbot_qq`
- Router 如果要识别“这是桥接来的消息”，可以优先看 `platform=qq`、`session_key`、Webhook headers 这些非自然语言信号。

## Dreamina Trigger Notes

- 命令型入口：`生成图片`, `生成视频`, `图片转视频`
- 自然语言 tool 描述里也明确提到了这些意图：
  - “画图、生成图片、制作插画”
  - “生成视频、动画、短片”
- 因此 Router 可以把“图片生成”和“视频生成”拆成两个高置信意图，再保留“图片转视频”作为独立强信号。

## Skills Index（可能需要 Router 分流）

- Apple: `apple-notes`, `apple-reminders`, `findmy`, `imessage`
- Autonomous agents: `claude-code`, `codex`, `hermes-agent`, `opencode`
- Creative: `architecture-diagram`, `ascii-art`, `ascii-video`, `creative-ideation`, `excalidraw`, `manim-video`, `p5js`, `popular-web-designs`, `songwriting-and-ai-music`
- Data science: `jupyter-live-kernel`
- DevOps: `webhook-subscriptions`
- Email: `himalaya`
- Gaming: `minecraft-modpack-server`, `pokemon-player`
- GitHub: `codebase-inspection`, `github-auth`, `github-code-review`, `github-issues`, `github-pr-workflow`, `github-repo-management`
- Leisure: `find-nearby`
- MCP: `mcporter`, `native-mcp`
- Media: `gif-search`, `heartmula`, `songsee`, `youtube-content`
- MLOps: `modal`, `lm-evaluation-harness`, `weights-and-biases`, `huggingface-hub`, `gguf`, `guidance`, `llama-cpp`, `obliteratus`, `outlines`, `vllm`, `audiocraft`, `clip`, `segment-anything`, `stable-diffusion`, `whisper`, `dspy`, `axolotl`, `grpo-rl-training`, `peft`, `pytorch-fsdp`, `trl-fine-tuning`, `unsloth`
- NAS: `nas`
- Note taking: `obsidian`
- Productivity: `google-workspace`, `linear`, `nano-pdf`, `notion`, `ocr-and-documents`, `powerpoint`
- Red teaming: `godmode`
- Research: `arxiv`, `blogwatcher`, `llm-wiki`, `polymarket`, `research-paper-writing`
- Smart home: `openhue`
- Social media: `xitter`
- Software development: `plan`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `writing-plans`

## Router Design Hints

- 命令前缀 `/task` 已经足够强，优先走规则路由，不必交给 LLM 二次判断。
- Dreamina 适合做“视觉生成”专槽，尤其是包含“生成图片 / 生成视频 / 图片转视频”的短句。
- Hermes bridge 更适合作为消息来源标签，不建议和用户意图分类混在同一层。
- Skills index 很适合做二阶段路由：先分大类，再在类内根据 skill slug 或关键词精排。
