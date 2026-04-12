# astrbot

This directory is reserved for the front-end shell layer.

Responsibilities:

- QQ / AstrBot message adaptation
- command entrypoints
- upload hooks
- role prompts
- rendering and reply formatting
- permission-facing interaction rules
- front-end runtime bridge files
- front-end shared plugin helpers
- compatibility plugin shells

Explicit non-responsibilities:

- backend skill execution logic
- backend memory ownership
- full workflow orchestration

Layout:

- `runtime/`
  - front-end bridge/runtime glue from `jw_claw/astrbot`
- `shared/`
  - shared helper modules for plugin shells
- `plugins/`
  - command/plugin shells that forward into backend and Harness
