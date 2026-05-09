from __future__ import annotations


def build_feature_flags_text(status: dict[str, bool]) -> str:
    lines = ["功能标志状态", ""]
    for flag, enabled in status.items():
        icon = "✅" if enabled else "❌"
        lines.append(f"{icon} {flag}: {'启用' if enabled else '禁用'}")
    return "\n".join(lines)


def build_missing_input_prompt(action: str, example: str) -> str:
    return f"{action}，例如: {example}"


def build_usage_text(usage: str) -> str:
    return f"使用格式: {usage}"


def build_error_text(action: str, error: Exception) -> str:
    return f"{action}失败: {error}"


def build_available_modes_text() -> str:
    return "可用模式: default, plan, bypass, auto"


def build_section_lines(title: str) -> list[str]:
    return [title, ""]


def collect_unique_labels(items, label_getter) -> list[str]:
    labels = []
    for item in items:
        label = label_getter(item)
        if label not in labels:
            labels.append(label)
    return labels


def build_category_summary_lines(title: str, categories: list[str]) -> list[str]:
    if not categories:
        return []
    return [title, "", "分类: " + ", ".join(categories), ""]


def build_priority_focus_text(category: str, suggestion: str) -> str:
    return f"优先关注: {category} | 建议: {suggestion}"


def build_feature_toggle_prompt(action: str, example: str) -> str:
    return f"请指定要{action}的功能标志，例如: {example}"


def build_feature_toggled_text(flag_name: str, enabled: bool) -> str:
    action = "启用" if enabled else "禁用"
    return f"✅ 已{action}功能: {flag_name}"


def build_task_created_text(task_id: str) -> str:
    return f"✅ 已创建任务: {task_id}"


def build_memory_added_text(memory_id: str) -> str:
    return f"✅ 已添加记忆 (ID: {memory_id})"


def build_permission_added_text(pattern: str, allow: bool) -> str:
    icon = "✅" if allow else "❌"
    return f"{icon} 已添加权限规则: {pattern}"


def build_permission_mode_set_text(mode_str: str) -> str:
    return f"✅ 已设置权限模式: {mode_str}"


def build_memory_search_header(query: str) -> str:
    return f"🔍 记忆搜索: {query}"


def build_memory_search_empty_text() -> str:
    return "未找到匹配的记忆"


def build_project_context_prompt(example: str) -> str:
    return f"请输入客户或项目关键词，例如: {example}"


def build_harness_disabled_text(subject: str) -> str:
    return f"JW-Claw Harness 当前未启用，无法查看{subject}"


def get_task_status_icon(status_value: str) -> str:
    return {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "🚫",
    }.get(status_value, "❓")


def build_importance_stars(importance: float) -> str:
    return "⭐" * int(importance * 5)


def truncate_preview(text: str, limit: int = 50) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def build_task_lines(tasks, category_getter=None, followup_getter=None) -> list[str]:
    if not tasks:
        return ["暂无任务"]

    lines = []
    for task in tasks:
        status_icon = get_task_status_icon(task.status.value)
        task_prefix = ""
        if category_getter is not None:
            task_prefix = f"[{category_getter(task)}] "
        lines.append(f"{status_icon} {task.id}: {task_prefix}{task.type.value}")
        if followup_getter is not None:
            lines.append(f"   跟进: {followup_getter(task)}")
    return lines


def build_memory_lines(
    memories, category_getter=None, followup_getter=None, preview: bool = False
) -> list[str]:
    if not memories:
        return ["暂无记忆"]

    lines = []
    for index, memory in enumerate(memories, 1):
        importance = build_importance_stars(memory.importance)
        memory_prefix = ""
        if category_getter is not None:
            memory_prefix = f"[{category_getter(memory)}] "
        content = truncate_preview(memory.content) if preview else memory.content
        lines.append(f"{index}. [{importance}] {memory_prefix}{content}")
        if followup_getter is not None:
            lines.append(f"   跟进: {followup_getter(memory)}")
    return lines


def parse_permission_allow(action: str) -> bool:
    return action.lower() in ["allow", "true", "1", "yes"]


def resolve_permission_mode(mode_str: str, permission_mode_enum):
    mode_map = {
        "default": permission_mode_enum.DEFAULT,
        "plan": permission_mode_enum.PLAN,
        "bypass": permission_mode_enum.BYPASS,
        "auto": permission_mode_enum.AUTO,
    }
    return mode_map.get(mode_str.lower())


def build_permissions_text(rules, mode) -> str:
    lines = [f"权限规则 (模式: {mode.value})", ""]
    if not rules:
        lines.append("暂无权限规则")
        return "\n".join(lines)

    for index, rule in enumerate(rules, 1):
        icon = "✅" if rule.allow else "❌"
        lines.append(f"{index}. {icon} {rule.pattern}")
    return "\n".join(lines)
