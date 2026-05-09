# Lossless-Claw-Enhanced Integration Plan

## Goal

Integrate the useful ideas from `lossless-claw-enhanced` into `JW-Bot` as an AstrBot-native context management layer.

This is **not** a direct plugin port from OpenClaw.

The target outcome is:

- AstrBot remains the only host framework
- conversation and QQ routing remain in AstrBot
- `lossless-claw-enhanced` ideas become a reusable context subsystem
- later memory and Harness work can build on top of the same context contract

## Why This Is First

The current AstrBot stack already has:

- conversation persistence in [`conversation_mgr.py`](/Users/dianchi/DC-Agent/astrbot/core/conversation_mgr.py)
- a pluggable context pipeline in [`manager.py`](/Users/dianchi/DC-Agent/astrbot/core/agent/context/manager.py)
- a `ContextCompressor` protocol in [`compressor.py`](/Users/dianchi/DC-Agent/astrbot/core/agent/context/compressor.py)
- a replaceable token counter in [`token_counter.py`](/Users/dianchi/DC-Agent/astrbot/core/agent/context/token_counter.py)

That means `lossless-claw-enhanced` fits naturally as a context-layer upgrade.

## Current AstrBot Baseline

AstrBot currently handles overflow with two simple strategies:

1. `TruncateByTurnsCompressor`
2. `LLMSummaryCompressor`

Current limitations:

- token estimation is heuristic and too weak for CJK-heavy workloads
- summaries are single-pass and overwrite detailed history in the active context shape
- there is no DAG summary hierarchy
- there is no explicit summary/message replacement index
- there is no recall tool equivalent to `lcm_expand`

These gaps are exactly where `lossless-claw-enhanced` helps most.

## What To Reuse

The following ideas should be reused conceptually:

1. **CJK-aware token estimation**
   Replace the current simple estimator with a stronger estimator tuned for Chinese-heavy usage.

2. **Lossless compaction**
   Do not only truncate old turns. Compact them into durable summary nodes while preserving source recoverability.

3. **Summary DAG**
   Keep leaf summaries and condensed summaries as separate tiers instead of flattening everything into one summary blob.

4. **Fresh tail protection**
   Always protect recent raw messages from compaction.

5. **Expansion / recall tools**
   Add AstrBot-side tools to recover detail from compacted history instead of assuming the summary is always enough.

6. **Operation serialization**
   Ensure compaction and ingest do not race inside the same conversation.

## What Not To Port Directly

The following parts are OpenClaw-specific and should be rewritten:

1. OpenClaw plugin packaging and slot registration
2. OpenClaw gateway lifecycle hooks
3. OpenClaw auth profile resolution
4. OpenClaw session JSONL reconciliation
5. OpenClaw-specific tool wiring and session delegation assumptions

## JW-Bot Target Architecture

The AstrBot-native version should land in a new context module family under:

- [`astrbot/core/agent/context/`](/Users/dianchi/DC-Agent/astrbot/core/agent/context)
- optional storage helpers under a new subtree such as `astrbot/core/context_store/`

Recommended new components:

1. `astrbot/core/agent/context/lossless_token_counter.py`
   CJK-aware token counting.

2. `astrbot/core/agent/context/lossless_compressor.py`
   AstrBot-facing compressor implementing the `ContextCompressor` protocol.

3. `astrbot/core/agent/context/lossless_store.py`
   Storage facade for raw messages, summary nodes, links, and context items.

4. `astrbot/core/agent/context/lossless_assembler.py`
   Rebuilds model-facing context from summary DAG + fresh tail.

5. `astrbot/core/agent/context/lossless_expand.py`
   Query and expansion helpers for recall.

6. `astrbot/core/agent/context/lossless_queue.py`
   Per-conversation mutation serialization.

## Integration Points

### 1. Token Counter

First upgrade the default token counter path used by [`manager.py`](/Users/dianchi/DC-Agent/astrbot/core/agent/context/manager.py).

Plan:

- add a new CJK-aware token counter
- allow configuration to choose `estimate` vs `lossless`
- eventually make the improved counter the default for Chinese-facing deployments

### 2. Compressor

`lossless-claw-enhanced` should plug in through `ContextConfig.custom_compressor`.

That keeps the current AstrBot API stable while replacing the internal strategy.

Plan:

- preserve the `ContextCompressor` interface
- make the new compressor assemble summary-backed context instead of emitting one summary pair
- keep a safe fallback to current truncation behavior

### 3. Conversation Storage

AstrBot already persists conversation history in [`conversation_mgr.py`](/Users/dianchi/DC-Agent/astrbot/core/conversation_mgr.py), but the current model is too flat for DAG compaction.

Plan:

- keep AstrBot conversations as the session anchor
- add a separate lossless context store keyed by AstrBot `conversation_id`
- do not replace `data_v4.db` immediately
- treat the new store as a sidecar index during phase 1

### 4. Agent Recall

Later phases should expose recall tools comparable to:

- `lcm_grep`
- `lcm_describe`
- `lcm_expand`

In AstrBot terms, these should become:

- built-in agent tools
- or a thin local plugin command surface for admin inspection

## Suggested Delivery Phases

### Phase 1A: Safer Token Counting

Deliver:

- CJK-aware token counter
- config switch for using it
- tests for Chinese / mixed-language / emoji-heavy conversations

This is the lowest-risk and highest-value first slice.

### Phase 1B: Lossless Store Sidecar

Deliver:

- sidecar tables or sidecar SQLite file for raw message and summary metadata
- per-conversation ingest synchronization
- no model-facing behavior change yet

This gives us observability before behavior changes.

### Phase 1C: Lossless Compressor

Deliver:

- AstrBot `custom_compressor` backed by sidecar store
- fresh-tail protection
- leaf compaction only
- fallback to truncation if compaction fails

Do not implement full DAG condensation in the first pass.

### Phase 1D: DAG Condensation + Recall

Deliver:

- condensed summary tiers
- summary expansion helpers
- admin-facing debug tools

This is the point where the integration becomes feature-complete.

## Phase 1 Scope Decision

For `JW-Bot`, the first implementation step should be:

**Phase 1A: replace AstrBot's current token estimation with a CJK-aware counter.**

Reason:

- smallest surface area
- immediately improves Chinese QQ usage
- zero dependency on OpenClaw plugin runtime
- reduces overflow risk before deeper memory/Harness work

## Risks

1. **Over-porting**
   If we try to port all of `lossless-claw-enhanced` at once, we will reintroduce OpenClaw assumptions into AstrBot.

2. **Store duplication**
   If the sidecar store and AstrBot conversation store diverge, context assembly will become unreliable.

3. **Premature DAG complexity**
   DAG condensation is valuable, but it should come after token counting and sidecar ingest are stable.

4. **Tool exposure too early**
   Expansion tools should not be exposed to all users before safety and scope rules are clear.

## Immediate Next Step

Start implementation with:

1. a new AstrBot CJK-aware token counter
2. tests comparing old and new estimation behavior
3. a config flag to enable the improved counter in `JW-Bot`

That is the cleanest way to begin phase 1 without destabilizing the running bot.
