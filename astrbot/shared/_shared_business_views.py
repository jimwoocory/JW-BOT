from __future__ import annotations

import re
from typing import Iterable


_PLACEHOLDER_PATTERNS = [
    "离线回退",
    "营销方案",
    "营销策划",
    "竞品分析",
    "方案暂缓",
    "问题诊断",
    "要求包含",
    "输出结构化",
    "发布时机",
    "舆论风险",
    "kpi",
    "渠道组合",
    "传播主张",
    "客户上下文",
    "数据来源",
    "建议下一步",
    "搜索焦点",
    "任务结果",
]


def strip_self_command_prefix(raw_text: str, command_name: str) -> str:
    text = (raw_text or "").strip()
    for prefix in (f"/{command_name}", command_name):
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            return text[len(prefix) :].strip()
    return text


def build_topic_aliases(topic: str) -> list[str]:
    aliases: list[str] = []
    text = (topic or "").strip()
    if not text:
        return aliases

    aliases.append(text)
    normalized = text.replace("今天", "").replace("最新动态", "").strip()
    if normalized and normalized not in aliases:
        aliases.append(normalized)

    known_aliases = {
        "柳州五菱": ["五菱", "上汽通用五菱"],
        "五菱": ["柳州五菱", "上汽通用五菱"],
        "上汽通用五菱": ["五菱", "柳州五菱"],
        "柳汽东风": ["柳汽", "东风柳汽", "东风风行"],
        "新能源汽车": ["新能源", "电车", "纯电", "混动"],
    }
    for key, values in known_aliases.items():
        if key in text:
            for value in values:
                if value not in aliases:
                    aliases.append(value)

    for chunk in re.split(r"\s+", text):
        chunk = chunk.strip()
        if len(chunk) >= 2 and chunk not in aliases:
            aliases.append(chunk)
    return aliases


def _clean_line(line: str) -> str:
    text = (line or "").strip()
    text = re.sub(r"^[#>*\-\s]+", "", text)
    text = text.strip("`").strip()
    return text


def _looks_like_placeholder(line: str) -> bool:
    lowered = line.lower()
    if not lowered:
        return True
    if lowered in {"[ok]", "ok", "unused"}:
        return True
    if re.match(r"^[一二三四五六七八九十]+、", line):
        return True
    if re.match(r"^\d+(\.\d+)*\s", line):
        return True
    if line.startswith("|") or "---" in line:
        return True
    return any(pattern in lowered for pattern in _PLACEHOLDER_PATTERNS)


def extract_relevant_lines(text: str, topic: str, max_items: int = 4) -> list[str]:
    aliases = [alias.lower() for alias in build_topic_aliases(topic)]
    items: list[str] = []
    generic_items: list[str] = []

    for raw_line in (text or "").splitlines():
        line = _clean_line(raw_line)
        if _looks_like_placeholder(line):
            continue
        if len(line) < 10:
            continue
        if len(line) > 180:
            continue

        lowered = line.lower()
        if aliases and any(alias in lowered for alias in aliases):
            if line not in items:
                items.append(line)
            continue

        if re.search(
            r"(20\d{2}|昨日|今日|今天|发布|宣布|销量|上市|门店|交付|渠道|品牌)", line
        ):
            if line not in generic_items:
                generic_items.append(line)

    merged = items + [line for line in generic_items if line not in items]
    return merged[:max_items]


def has_reliable_lines(lines: Iterable[str], min_count: int = 2) -> bool:
    return len([line for line in lines if (line or "").strip()]) >= min_count


def build_business_brief(
    topic: str,
    news_lines: list[str],
    hot_lines: list[str],
    source_notes: list[str],
) -> str:
    lines = [
        f"【业务简报】{topic}",
        "",
        "今日要点",
    ]

    if news_lines:
        lines.extend(f"- {item}" for item in news_lines)

    if hot_lines:
        lines.append("")
        lines.append("传播关注点")
        lines.extend(f"- {item}" for item in hot_lines)

    if source_notes:
        lines.append("")
        lines.append("信息来源")
        lines.extend(f"- {item}" for item in source_notes)

    return "\n".join(lines)


def build_no_reliable_data_text(topic: str, reasons: list[str]) -> str:
    lines = [
        f"【业务简报】{topic}",
        "",
        "今天没有整理出足够可靠的可交付信息。",
        "原因",
    ]
    lines.extend(f"- {reason}" for reason in reasons if reason)
    lines.extend(
        [
            "",
            "处理原则",
            "- 宁可不给结论，也不使用模板化或疑似失真的内容充数。",
            "- 建议先确认检索源和时间窗口，再重新生成。",
        ]
    )
    return "\n".join(lines)
