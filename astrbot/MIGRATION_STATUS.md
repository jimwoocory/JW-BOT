# astrbot Migration Status

## Status

This directory now contains the first front-end shell consolidation snapshot for `JW-claw`.

Copied front-end runtime assets:

- `runtime/` from `jw_claw/astrbot/`

Copied shared shell helpers:

- `_shared_business_views.py`
- `_shared_core_state.py`
- `_shared_feature_flags.py`
- `_shared_harness_bridge.py`
- `_shared_marketing_legacy.py`
- `_shared_ops_helpers.py`

Copied active shell plugins:

- `plugins/marketing_opencli/`
- `plugins/marketing_tools/`
- `plugins/openclaw_core_v2/`
- `plugins/openclaw_briefing/`
- `plugins/openclaw_knowledge_ingest/`
- `plugins/opencli/`

## Meaning

This is the first front-end consolidation step for the new `JW-claw` project shape.

It establishes one future front-end home for:

- message adaptation
- shell command entry
- plugin rendering
- front-end compatibility behavior

## Important Note

This is not yet the active runtime path.

Current imports and runtime still depend on the existing repository layout until later migration steps rewrite those paths.

## Next Recommended Step

1. define which front-end plugins remain active shells
2. reduce duplicated shell behavior across compatibility plugins
3. identify compatibility shims required for import/path rewrites
4. then start controlled front-end import rewrites in small batches
