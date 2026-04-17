from __future__ import annotations

import os


DEFAULT_FEATURE_FLAG_NAMES = (
    "RAGFLOW",
    "ASTRBOT",
    "CLAWTEAM",
    "STAR_OFFICE_UI",
    "LOSSLESS_CONTEXT",
)


def create_feature_flags() -> dict[str, bool]:
    return {
        name: os.getenv(f"OPENCLAW_{name}", "true").lower() == "true"
        for name in DEFAULT_FEATURE_FLAG_NAMES
    }


def is_feature_enabled(flags: dict[str, bool], flag_name: str) -> bool:
    return flags.get(flag_name, False)


def enable_feature(flags: dict[str, bool], flag_name: str):
    if flag_name in flags:
        flags[flag_name] = True


def disable_feature(flags: dict[str, bool], flag_name: str):
    if flag_name in flags:
        flags[flag_name] = False


def get_feature_status(flags: dict[str, bool]) -> dict[str, bool]:
    return flags.copy()
