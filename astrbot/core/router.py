from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

LLMClassifier = Callable[[str, str, dict[str, Any]], Awaitable[str | None]]


@dataclass(slots=True)
class Intent:
    category: str
    intent_type: str
    confidence: float
    workflow_kind: str | None = None
    skill_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RouterRule:
    category: str
    intent_type: str
    confidence: float
    pattern: str | None = None
    keywords: list[str] = field(default_factory=list)
    workflow_kind: str | None = None
    skill_name: str | None = None
    command_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def match(self, message: str) -> bool:
        normalized = _normalize(message)
        if self.pattern:
            normalized_pattern = _normalize(self.pattern)
            if normalized_pattern.startswith("/"):
                if normalized.startswith(normalized_pattern):
                    return True
            elif normalized_pattern in normalized:
                return True
        if self.keywords:
            message_lower = normalized
            return any(keyword.lower() in message_lower for keyword in self.keywords)
        return False

    @property
    def specificity(self) -> int:
        if self.pattern:
            return len(self.pattern)
        return max((len(keyword) for keyword in self.keywords), default=0)


class IntentRouter:
    def __init__(
        self,
        config: dict[str, Any],
        llm_provider: LLMClassifier | None = None,
    ) -> None:
        self.config = config
        self.llm_provider = llm_provider
        self.fallback_threshold = float(config.get("fallback_threshold", 0.75))
        self.task_rules = self._load_rules(config.get("task_intents", []), "task")
        self.skill_rules = self._load_rules(config.get("skill_intents", []), "skill")
        self.llm_fallback_prompt = (
            (config.get("llm_fallback", {}) or {}).get("system_prompt", "").strip()
        )

    @classmethod
    def from_yaml(
        cls,
        path: Path,
        llm_provider: LLMClassifier | None = None,
    ) -> IntentRouter:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(payload, llm_provider=llm_provider)

    async def classify(self, message: str, context: dict[str, Any]) -> Intent:
        text = (message or "").strip()
        if not text:
            return self._default_intent(context)

        transport_metadata = self._transport_metadata(context)
        matched = self._match_rules(text, transport_metadata)
        if matched and matched.confidence >= self.fallback_threshold:
            return matched

        llm_intent = await self._classify_with_llm(text, context, transport_metadata)
        if llm_intent and (
            matched is None or llm_intent.confidence >= matched.confidence
        ):
            return llm_intent

        if matched is not None:
            return matched
        return self._default_intent(context, transport_metadata)

    def _load_rules(
        self,
        rules: list[dict[str, Any]],
        default_category: str,
    ) -> list[RouterRule]:
        loaded: list[RouterRule] = []
        for item in rules:
            loaded.append(
                RouterRule(
                    category=str(item.get("category", default_category)),
                    intent_type=str(item.get("intent_type", "general")),
                    confidence=float(item.get("confidence", 0.5)),
                    pattern=item.get("pattern"),
                    keywords=list(item.get("keywords", [])),
                    workflow_kind=item.get("workflow_kind"),
                    skill_name=item.get("skill_name"),
                    command_name=item.get("command_name"),
                    metadata=dict(item.get("metadata", {})),
                )
            )
        return loaded

    def _match_rules(
        self,
        message: str,
        transport_metadata: dict[str, Any],
    ) -> Intent | None:
        best_rule: RouterRule | None = None
        for rule in [*self.task_rules, *self.skill_rules]:
            if rule.match(message):
                if best_rule is None or (
                    rule.confidence,
                    rule.specificity,
                ) > (
                    best_rule.confidence,
                    best_rule.specificity,
                ):
                    best_rule = rule

        if best_rule is None:
            return None

        metadata = dict(best_rule.metadata)
        metadata.update(transport_metadata)
        metadata["matched_by"] = "rule"
        if best_rule.command_name:
            metadata["command_name"] = best_rule.command_name
            extracted_prompt = _extract_prompt_from_message(
                message,
                best_rule.command_name,
                best_rule.intent_type,
            )
            if extracted_prompt:
                metadata["synthetic_command"] = (
                    f"{best_rule.command_name} {extracted_prompt}".strip()
                )
                metadata["synthetic_prompt"] = extracted_prompt

        return Intent(
            category=best_rule.category,
            intent_type=best_rule.intent_type,
            confidence=best_rule.confidence,
            workflow_kind=best_rule.workflow_kind,
            skill_name=best_rule.skill_name,
            metadata=metadata,
        )

    async def _classify_with_llm(
        self,
        message: str,
        context: dict[str, Any],
        transport_metadata: dict[str, Any],
    ) -> Intent | None:
        if self.llm_provider is None or not self.llm_fallback_prompt:
            return None

        prompt = (
            "请将以下用户消息分类为 task、skill 或 conversation，并只返回 JSON。\n"
            "用户消息：\n"
            f"{message}\n\n"
            "当前上下文：\n"
            f"{json.dumps(context, ensure_ascii=False)}"
        )
        raw = await self.llm_provider(self.llm_fallback_prompt, prompt, context)
        if not raw:
            return None

        parsed = _parse_json_payload(raw)
        if not isinstance(parsed, dict):
            return None

        metadata = dict(parsed.get("metadata", {}))
        metadata.update(transport_metadata)
        metadata["matched_by"] = "llm"

        return Intent(
            category=str(parsed.get("category", "conversation")),
            intent_type=str(parsed.get("intent_type", "general")),
            confidence=float(parsed.get("confidence", 0.5)),
            workflow_kind=parsed.get("workflow_kind"),
            skill_name=parsed.get("skill_name"),
            metadata=metadata,
        )

    def _default_intent(
        self,
        context: dict[str, Any],
        transport_metadata: dict[str, Any] | None = None,
    ) -> Intent:
        metadata = dict(transport_metadata or {})
        if context.get("activated_handler_count"):
            metadata["activated_handler_count"] = context["activated_handler_count"]
        return Intent(
            category="conversation",
            intent_type="general",
            confidence=0.4,
            metadata=metadata,
        )

    def _transport_metadata(self, context: dict[str, Any]) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if context.get("platform_id") == "qqbot":
            metadata["platform"] = "qqbot"
        if context.get("session_key"):
            metadata["transport"] = "hermes_bridge"
            metadata["session_key"] = context.get("session_key")
        webhook_event = context.get("webhook_event")
        if webhook_event:
            metadata["webhook_event"] = webhook_event
        return metadata


def _extract_prompt_from_message(
    message: str,
    command_name: str,
    intent_type: str,
) -> str:
    text = re.sub(r"\s+", " ", message).strip()
    if _normalize(text).startswith(_normalize(command_name)):
        text = text[len(command_name) :].strip()

    polite_prefixes = [
        "帮我",
        "请",
        "麻烦",
        "能不能",
        "可以",
        "帮",
        "给我",
        "来个",
        "来一张",
        "来一段",
    ]
    for prefix in polite_prefixes:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()

    replacements = {
        "dreamina_image": [
            "画一张",
            "做一张图",
            "生成图片",
            "做个海报",
            "制作插画",
            "画图",
        ],
        "dreamina_video": ["生成视频", "做个视频", "生成动画", "做个动画", "短片"],
        "dreamina_image2video": ["图片转视频"],
    }
    for phrase in replacements.get(intent_type, []):
        text = text.replace(phrase, "").strip()

    return text.strip(" ，。！？,.!?") or message.strip()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _parse_json_payload(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
        if match:
            text = match.group(1)

    if not text.startswith("{"):
        match = re.search(r"(\{.*\})", text, re.S)
        if match:
            text = match.group(1)

    try:
        data = json.loads(text)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


__all__ = ["Intent", "IntentRouter"]
