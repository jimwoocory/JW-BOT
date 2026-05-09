# JW-Bot Harness Landing Plan

## Goal

Land a single Harness implementation inside `JW-Bot`, with `AstrBot` remaining the only host framework.

This Harness is for company work, not a generic research framework.

It must serve:

- QQbot as the real user entrypoint
- enterprise promotion and delivery workflows
- long conversations through the existing lossless context layer
- future cross-session cognition through a shared memory layer

## Non-Goals

Do not introduce:

- a second host framework beside `AstrBot`
- an OpenClaw-style parallel runtime as the main control plane
- premature multi-agent orchestration for its own sake

## One-System Architecture

`JW-Bot` keeps one unified stack:

1. `AstrBot`
   host runtime, QQ routing, provider selection, plugin/tool execution

2. `lossless context`
   per-conversation context sidecar and compaction layer

3. `Harness`
   task lifecycle, execution trace, review trace, and operational visibility

4. `memory`
   later cross-session cognition layer built on top of the same contracts

## Company-First Scope

The first Harness slice must directly support company work:

- marketing and promotion task intake
- project/task decomposition
- execution trace collection
- result review / approval notes
- reusable delivery records

The first slice does **not** need:

- autonomous agent teams
- complex A2A delegation
- generalized planner research

## Phase Order

### Phase 1: Harness Sidecar Foundation

Create a dedicated Harness sidecar store inside `JW-Bot`.

Deliver:

- `harness_tasks` table
- `harness_task_events` table
- stable task status contract
- simple engine helpers for task creation and event recording

Why first:

- gives us inspectable task state
- does not disturb AstrBot core chat behavior
- creates the contract memory and review can build on later

### Phase 2: Task Entry Integration

Add AstrBot-native task entrypoints.

Deliver:

- create/update task from plugin or built-in command surface
- bind tasks to `conversation_id`, `platform_id`, and `session_id`
- store minimal task metadata for company workflows

### Phase 3: Review and Operational Views

Deliver:

- task event inspection APIs
- review checkpoints
- lightweight dashboard/debug visibility

### Phase 4: Cross-Session Cognition

Deliver:

- promote stable task outcomes into memory
- connect lossless summaries and memory retrieval to Harness execution

## Proposed File Layout

New code should live under:

- [`astrbot/core/harness/`](/Users/dianchi/DC-Agent/astrbot/core/harness)

Recommended initial modules:

- [`astrbot/core/harness/contracts.py`](/Users/dianchi/DC-Agent/astrbot/core/harness/contracts.py)
  stable dataclasses and status definitions

- [`astrbot/core/harness/task_store.py`](/Users/dianchi/DC-Agent/astrbot/core/harness/task_store.py)
  sidecar persistence for tasks and task events

- [`astrbot/core/harness/engine.py`](/Users/dianchi/DC-Agent/astrbot/core/harness/engine.py)
  thin task lifecycle helpers used by future plugins or built-in command paths

Tests should start under:

- [`tests/unit/test_harness_task_store.py`](/Users/dianchi/DC-Agent/tests/unit/test_harness_task_store.py)

## Stable Contract

The Harness task contract should stay simple at first.

### Task fields

- `task_id`
- `conversation_id`
- `platform_id`
- `session_id`
- `title`
- `domain`
- `status`
- `payload_json`
- `result_json`
- `created_at`
- `updated_at`

### Event fields

- `event_id`
- `task_id`
- `event_type`
- `payload_json`
- `created_at`

### Initial statuses

- `pending`
- `in_progress`
- `blocked`
- `review_required`
- `completed`
- `cancelled`
- `failed`

## Integration Rules

When we wire Harness into the runtime, keep these rules:

1. AstrBot remains the session anchor.
2. Lossless remains the conversation-history anchor.
3. Harness tracks task state, not raw chat history.
4. Memory promotion happens later from Harness outcomes, not from arbitrary chat noise.
5. All task traces must be inspectable from files or SQLite tables.

## Current Delivery Decision

Start with **Phase 1** only.

That means this first landing should create:

- a Harness sidecar database contract
- a task/event store
- a minimal engine API
- tests

This keeps us inside one system and gives the next phases a stable base.

## Runtime Hooks Added In This Phase

The first landing should also expose Harness through shared runtime objects:

- `AstrBotCoreLifecycle.harness_store`
- `AstrBotCoreLifecycle.harness_engine`
- `star.Context.harness_store`
- `star.Context.harness_engine`

And provide read-only dashboard APIs for inspection:

- `/api/harness/tasks/<conversation_id>`
- `/api/harness/task/<task_id>`
- `/api/harness/task/<task_id>/events`
