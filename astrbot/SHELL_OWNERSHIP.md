# JW-claw AstrBot Shell Ownership

## Final rule

AstrBot is the front-end shell layer.

It owns:

- message adaptation
- command entrypoints
- upload hook interaction
- role prompt application
- response rendering
- front-end compatibility shells

It does not own:

- backend skill execution
- backend memory engines
- backend runtime mechanics
- full business orchestration policy

## Current sub-areas

### `runtime/`

Owns:

- front-end bridge code
- front-end flags
- front-end LLM adapter glue

### `shared/`

Owns:

- plugin-shared helper modules
- front-end compatibility helpers
- shell-side rendering and shared state glue

### `plugins/`

Owns:

- active front-end shell plugins
- compatibility command surfaces
- front-end routing into backend/Harness

## Important rule

No file in this tree should become the long-term home for:

- memory ownership
- task runtime ownership
- backend skill source-of-truth

Those stay in `openclaw/` and are orchestrated by `HarnessEngineering/`.
