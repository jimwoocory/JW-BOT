from __future__ import annotations


def build_marketing_legacy_response(
    command_name: str,
    prompt: str,
    titles: dict[str, str],
    default_title: str,
    inline_title: bool = False,
) -> str:
    title = titles.get(command_name, default_title)
    if inline_title:
        header = f"{title} - {prompt}"
    else:
        header = f"{title}\n\n需求：{prompt}"
    return (
        f"{header}\n\n"
        "当前已切换到 Legacy 模板响应模式。\n"
        "如需恢复 JW-Claw Harness，请启用 OPENCLAW_JW_CLAW_HARNESS。"
    )
