from __future__ import annotations

import os


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def is_harness_enabled() -> bool:
    return _env_flag("OPENCLAW_JW_CLAW_HARNESS", "true")


def is_harness_debug_enabled() -> bool:
    return _env_flag("OPENCLAW_JW_CLAW_HARNESS_DEBUG", "true")


def is_astrbot_provider_bridge_enabled() -> bool:
    # Enabled by default to use AstrBot's LLM provider
    return _env_flag("OPENCLAW_JW_CLAW_USE_ASTRBOT_PROVIDER", "true")


def is_frontend_local_fallback_enabled() -> bool:
    return _env_flag("OPENCLAW_JW_CLAW_FRONTEND_LOCAL_FALLBACK", "true")
