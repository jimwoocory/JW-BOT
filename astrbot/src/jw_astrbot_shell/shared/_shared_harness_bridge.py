from __future__ import annotations

import inspect

from jw_astrbot_shell import HarnessAstrBotBridge, is_harness_enabled


async def _resolve_legacy_text(legacy_builder, command_name: str, prompt: str) -> str:
    fallback = legacy_builder(command_name, prompt)
    if inspect.isawaitable(fallback):
        return await fallback
    return fallback


async def get_harness_or_legacy_text(
    harness_bridge: HarnessAstrBotBridge,
    command_name: str,
    prompt: str,
    event,
    legacy_builder,
) -> str:
    # Prefer JW-Claw when enabled, but keep legacy templates as an availability fallback
    # so marketing commands still produce a usable response during bridge/runtime failures.
    if not is_harness_enabled():
        return await _resolve_legacy_text(legacy_builder, command_name, prompt)

    try:
        return await harness_bridge.handle_command_text(
            command_name,
            prompt=prompt,
            event=event,
        )
    except Exception:
        return await _resolve_legacy_text(legacy_builder, command_name, prompt)
