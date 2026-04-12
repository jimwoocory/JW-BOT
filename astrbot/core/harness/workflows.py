from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Literal

from .contracts import HarnessTaskCreateRequest

HarnessWorkflowKind = Literal[
    "marketing_plan",
    "content_delivery",
    "project_followup",
    "approval_request",
]

_WORKFLOW_TEMPLATES: dict[HarnessWorkflowKind, dict[str, Any]] = {
    "marketing_plan": {
        "domain": "marketing",
        "title_prefix": "营销策划",
        "review_required": True,
        "required_outputs": ["strategy", "channels", "timeline", "kpis"],
    },
    "content_delivery": {
        "domain": "delivery",
        "title_prefix": "内容交付",
        "review_required": True,
        "required_outputs": ["deliverables", "deadline", "owner"],
    },
    "project_followup": {
        "domain": "project",
        "title_prefix": "项目跟进",
        "review_required": False,
        "required_outputs": ["progress", "risks", "next_actions"],
    },
    "approval_request": {
        "domain": "approval",
        "title_prefix": "审批确认",
        "review_required": True,
        "required_outputs": ["decision", "owner", "blocking_reason"],
    },
}


@dataclass(slots=True)
class HarnessWorkflowPlan:
    workflow_kind: HarnessWorkflowKind
    title: str
    domain: str
    payload: dict[str, Any]


@dataclass(slots=True)
class HarnessWorkflowValidation:
    workflow_kind: HarnessWorkflowKind
    review_required: bool
    missing_outputs: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.missing_outputs


def build_workflow_plan(
    workflow_kind: HarnessWorkflowKind,
    brief: str,
    *,
    source: str,
    message_text: str,
) -> HarnessWorkflowPlan:
    template = _WORKFLOW_TEMPLATES[workflow_kind]
    cleaned_brief = brief.strip()
    title = f"{template['title_prefix']} | {cleaned_brief}" if cleaned_brief else str(
        template["title_prefix"]
    )
    payload = {
        "source": source,
        "message_text": message_text,
        "workflow_kind": workflow_kind,
        "brief": cleaned_brief,
        "review_required_by_default": template["review_required"],
        "required_outputs": list(template["required_outputs"]),
    }
    return HarnessWorkflowPlan(
        workflow_kind=workflow_kind,
        title=title,
        domain=str(template["domain"]),
        payload=payload,
    )


def create_workflow_request(
    workflow_kind: HarnessWorkflowKind,
    brief: str,
    *,
    conversation_id: str,
    platform_id: str,
    session_id: str,
    source: str,
    message_text: str,
) -> HarnessTaskCreateRequest:
    plan = build_workflow_plan(
        workflow_kind,
        brief,
        source=source,
        message_text=message_text,
    )
    return HarnessTaskCreateRequest(
        title=plan.title,
        conversation_id=conversation_id,
        platform_id=platform_id,
        session_id=session_id,
        domain=plan.domain,
        payload=plan.payload,
    )


def parse_workflow_result(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text:
        return {}
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {"summary": text}


def validate_workflow_result(
    payload: dict[str, Any],
    result: dict[str, Any],
) -> HarnessWorkflowValidation | None:
    workflow_kind = payload.get("workflow_kind")
    if workflow_kind not in _WORKFLOW_TEMPLATES:
        return None

    required_outputs = payload.get("required_outputs", []) or []
    missing_outputs = [
        key for key in required_outputs if not _has_meaningful_value(result.get(key))
    ]
    return HarnessWorkflowValidation(
        workflow_kind=workflow_kind,
        review_required=bool(payload.get("review_required_by_default", False)),
        missing_outputs=missing_outputs,
    )


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True
