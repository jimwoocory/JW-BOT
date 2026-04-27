# Plugin Health Report - 2026-04-18

| 插件 | 状态 | import 全部可达 | 注册名 | 备注 |
|------|------|----------------|--------|------|
| dreamina_plugin | ✅ Healthy | yes | `dreamina_plugin` | 模块可导入；运行期依赖外部 `dreamina` CLI。 |
| hermes_bridge | ❌ Broken | yes | `hermes_bridge` | `astrbot/plugins/hermes_bridge/__init__.py` 的 `@register(...)` 缺少第 4 个 `version` 参数，导入时报 `TypeError: register_star() missing 1 required positional argument: 'version'`。建议补上版本号后再验证加载。 |
| minimax_token_plugin | ✅ Healthy | yes | `minimax_token_plugin` | 模块可导入；运行期依赖 `config.json` 中的 API Key。 |
| openclaw_file_ingest | ✅ Healthy | yes | `openclaw_file_ingest` | 模块可导入；默认知识库根目录回退到硬编码绝对路径，部署时建议显式设置 `OPENCLAW_KNOWLEDGE_ROOT`。 |
| opencli | ✅ Healthy | yes | `opencli` | 模块可导入；运行期依赖系统 PATH 中存在 `opencli`。 |

## Verification Notes

- Static imports for all five active plugins resolve successfully.
- Module import smoke test succeeds for `dreamina_plugin`, `minimax_token_plugin`, `openclaw_file_ingest`, and `opencli`.
- Module import smoke test fails for `hermes_bridge` because the registration decorator signature is incomplete, even though its imported modules are all reachable.
