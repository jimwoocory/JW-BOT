from astrbot.core.harness import (
    build_workflow_plan,
    create_workflow_request,
    parse_workflow_result,
    validate_workflow_result,
)


def test_build_workflow_plan_for_marketing_plan():
    plan = build_workflow_plan(
        "marketing_plan",
        "制定本周五菱推广计划",
        source="workflow_intake",
        message_text="/task intake marketing_plan 制定本周五菱推广计划",
    )

    assert plan.domain == "marketing"
    assert plan.title.startswith("营销策划 | ")
    assert plan.payload["workflow_kind"] == "marketing_plan"
    assert plan.payload["review_required_by_default"] is True
    assert "kpis" in plan.payload["required_outputs"]


def test_create_workflow_request_keeps_runtime_binding_fields():
    request = create_workflow_request(
        workflow_kind="project_followup",
        brief="整理客户本周推进情况",
        conversation_id="conv-1",
        platform_id="qq",
        session_id="qq:friend:1",
        source="workflow_intake",
        message_text="/task intake project_followup 整理客户本周推进情况",
    )

    assert request.conversation_id == "conv-1"
    assert request.platform_id == "qq"
    assert request.session_id == "qq:friend:1"
    assert request.domain == "project"
    assert request.payload["workflow_kind"] == "project_followup"


def test_parse_workflow_result_supports_json_payload():
    result = parse_workflow_result('{"strategy":"A","channels":["小红书"],"timeline":"本周","kpis":["曝光"]}')
    assert result["strategy"] == "A"
    assert result["channels"] == ["小红书"]


def test_validate_workflow_result_reports_missing_fields():
    request = create_workflow_request(
        workflow_kind="marketing_plan",
        brief="制定推广计划",
        conversation_id="conv-1",
        platform_id="qq",
        session_id="qq:friend:1",
        source="workflow_intake",
        message_text="/task intake marketing_plan 制定推广计划",
    )
    validation = validate_workflow_result(
        request.payload,
        {"strategy": "A", "timeline": "本周"},
    )
    assert validation is not None
    assert validation.is_valid is False
    assert set(validation.missing_outputs) == {"channels", "kpis"}
