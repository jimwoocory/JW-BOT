"""
Router 单元测试 — SessionRouter & IntentRouter.

Task 1 — 对现有 SessionRouter 写完整覆盖测试。
Task 1b — IntentRouter 完整单元测试。
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from astrbot.core.router import (
    Intent,
    IntentRouter,
    RouterRule,
    _normalize,
    _parse_json_payload,
    _extract_prompt_from_message,
)
from astrbot.plugins.hermes_bridge.router import (
    SessionRouter,
    PlatformUser,
    PlatformType,
    SessionInfo,
)

# ============================================================================
# Section 1: PlatformType
# ============================================================================


def test_platform_type_values():
    """PlatformType 应包含所有预期的平台枚举值。"""
    assert PlatformType.WEBUI.value == "webui"
    assert PlatformType.QQ.value == "qq"
    assert PlatformType.TELEGRAM.value == "telegram"
    assert PlatformType.DISCORD.value == "discord"
    assert PlatformType.SLACK.value == "slack"
    assert PlatformType.WHATSAPP.value == "whatsapp"
    assert PlatformType.HOMEASSISTANT.value == "homeassistant"
    assert PlatformType.SIGNAL.value == "signal"


def test_platform_type_from_string_exact():
    """from_string 应精确匹配大写键名。"""
    assert PlatformType.from_string("QQ") == PlatformType.QQ
    assert PlatformType.from_string("WEBUI") == PlatformType.WEBUI


def test_platform_type_from_string_case_insensitive():
    """from_string 应大小写不敏感。"""
    assert PlatformType.from_string("qq") == PlatformType.QQ
    assert PlatformType.from_string("Telegram") == PlatformType.TELEGRAM
    assert PlatformType.from_string("discord") == PlatformType.DISCORD


def test_platform_type_from_string_fuzzy():
    """from_string 应通过 value 模糊匹配。"""
    assert PlatformType.from_string("webui") == PlatformType.WEBUI
    assert PlatformType.from_string("whatsapp") == PlatformType.WHATSAPP


def test_platform_type_from_string_invalid():
    """from_string 对未知值应抛出 ValueError。"""
    with pytest.raises(ValueError):
        PlatformType.from_string("unknown_platform")


# ============================================================================
# Section 2: PlatformUser
# ============================================================================


def test_platform_user_generate_id_without_channel():
    """无 channel_id 时应生成 platform:user_id 格式。"""
    user = PlatformUser(platform=PlatformType.QQ, user_id="123456")
    assert user.generate_id() == "qq:123456"


def test_platform_user_generate_id_with_channel():
    """有 channel_id 时应生成 platform:user_id:channel_id 格式。"""
    user = PlatformUser(
        platform=PlatformType.TELEGRAM,
        user_id="789",
        channel_id="group_abc",
    )
    assert user.generate_id() == "telegram:789:group_abc"


def test_platform_user_to_dict():
    """to_dict 应返回包含所有字段的字典。"""
    user = PlatformUser(
        platform=PlatformType.DISCORD,
        user_id="u1",
        channel_id="ch1",
        metadata={"key": "value"},
    )
    d = user.to_dict()
    assert d["platform"] == PlatformType.DISCORD
    assert d["user_id"] == "u1"
    assert d["channel_id"] == "ch1"
    assert d["metadata"] == {"key": "value"}


def test_platform_user_from_dict():
    """from_dict 应正确还原 PlatformUser 对象。"""
    d = {
        "platform": "slack",
        "user_id": "u2",
        "channel_id": "ch2",
        "metadata": {"foo": "bar"},
    }
    user = PlatformUser.from_dict(d)
    assert user.platform == PlatformType.SLACK
    assert user.user_id == "u2"
    assert user.channel_id == "ch2"
    assert user.metadata == {"foo": "bar"}


# ============================================================================
# Section 3: SessionRouter — 核心 CRUD
# ============================================================================


@pytest.fixture
def router(tmp_path):
    """创建使用临时数据库的 SessionRouter。"""
    db = tmp_path / "test_router.db"
    return SessionRouter(str(db))


def test_get_or_create_session_new(router):
    """首次调用 get_or_create_session 应创建新会话。"""
    user = PlatformUser(platform=PlatformType.QQ, user_id="test_user_1")
    session_id = router.get_or_create_session(user)
    assert session_id is not None
    assert len(session_id) == 12  # uuid4 hex[:12]


def test_get_or_create_session_reuse(router):
    """同一用户再次调用应返回相同的 session_id。"""
    user = PlatformUser(platform=PlatformType.WEBUI, user_id="web_user_1")
    sid1 = router.get_or_create_session(user)
    sid2 = router.get_or_create_session(user)
    assert sid1 == sid2


def test_get_or_create_session_different_users(router):
    """不同用户应获得不同的 session_id。"""
    user_a = PlatformUser(platform=PlatformType.QQ, user_id="user_a")
    user_b = PlatformUser(platform=PlatformType.QQ, user_id="user_b")
    sid_a = router.get_or_create_session(user_a)
    sid_b = router.get_or_create_session(user_b)
    assert sid_a != sid_b


def test_get_or_create_session_same_user_different_channel(router):
    """同一用户不同频道应创建不同会话。"""
    user1 = PlatformUser(platform=PlatformType.TELEGRAM, user_id="tg1", channel_id="ch_a")
    user2 = PlatformUser(platform=PlatformType.TELEGRAM, user_id="tg1", channel_id="ch_b")
    sid1 = router.get_or_create_session(user1)
    sid2 = router.get_or_create_session(user2)
    assert sid1 != sid2


def test_get_session_by_platform_user_existing(router):
    """已存在的用户应返回 session_id。"""
    user = PlatformUser(platform=PlatformType.DISCORD, user_id="discord_1")
    router.get_or_create_session(user)
    result = router.get_session_by_platform_user(user)
    assert result is not None
    assert len(result) == 12


def test_get_session_by_platform_user_nonexistent(router):
    """不存在的用户应返回 None。"""
    user = PlatformUser(platform=PlatformType.SLACK, user_id="never_existed")
    assert router.get_session_by_platform_user(user) is None


def test_get_platform_user_by_session(router):
    """通过 session_id 应能反查 PlatformUser。"""
    original = PlatformUser(
        platform=PlatformType.WHATSAPP,
        user_id="wa_user",
        channel_id="wa_group",
        metadata={"note": "test"},
    )
    sid = router.get_or_create_session(original)
    retrieved = router.get_platform_user_by_session(sid)
    assert retrieved is not None
    assert retrieved.platform == PlatformType.WHATSAPP
    assert retrieved.user_id == "wa_user"
    assert retrieved.channel_id == "wa_group"


def test_get_platform_user_by_session_nonexistent(router):
    """不存在的 session_id 应返回 None。"""
    assert router.get_platform_user_by_session("000000000000") is None


# ============================================================================
# Section 4: SessionRouter — 列表查询
# ============================================================================


def test_list_all_sessions_empty(router):
    """数据库为空时应返回空列表。"""
    assert router.list_all_sessions() == []


def test_list_all_sessions_with_data(router):
    """创建多个会话后应能列出。"""
    for i in range(3):
        user = PlatformUser(platform=PlatformType.QQ, user_id=f"list_user_{i}")
        router.get_or_create_session(user)
    sessions = router.list_all_sessions()
    assert len(sessions) == 3
    # 每个 entry 应有必要字段
    for s in sessions:
        assert "session_id" in s
        assert "platform" in s
        assert "platform_user_id" in s


def test_list_sessions_by_platform(router):
    """按平台过滤应只返回对应平台的会话。"""
    qq_user = PlatformUser(platform=PlatformType.QQ, user_id="qq_list")
    tg_user = PlatformUser(platform=PlatformType.TELEGRAM, user_id="tg_list")
    router.get_or_create_session(qq_user)
    router.get_or_create_session(tg_user)

    qq_sessions = router.list_sessions_by_platform(PlatformType.QQ)
    tg_sessions = router.list_sessions_by_platform(PlatformType.TELEGRAM)

    assert len(qq_sessions) == 1
    assert len(tg_sessions) == 1
    assert qq_sessions[0]["platform"] == "qq"
    assert tg_sessions[0]["platform"] == "telegram"


def test_list_all_sessions_limit(router):
    """limit 参数应限制返回数量。"""
    for i in range(5):
        user = PlatformUser(platform=PlatformType.QQ, user_id=f"limit_user_{i}")
        router.get_or_create_session(user)
    sessions = router.list_all_sessions(limit=2)
    assert len(sessions) == 2


# ============================================================================
# Section 5: SessionRouter — 标题与删除
# ============================================================================


def test_set_session_title(router):
    """设置会话标题应成功并返回 True。"""
    user = PlatformUser(platform=PlatformType.QQ, user_id="title_user")
    sid = router.get_or_create_session(user)
    result = router.set_session_title(sid, "My Important Chat")
    assert result is True
    # 验证标题已更新
    info = router.get_session_info(sid)
    assert info is not None
    assert info.title == "My Important Chat"


def test_set_session_title_nonexistent(router):
    """对不存在的 session_id 设置标题应返回 False。"""
    assert router.set_session_title("does_not_exist_00", "title") is False


def test_delete_session(router):
    """删除会话应成功。"""
    user = PlatformUser(platform=PlatformType.QQ, user_id="delete_user")
    sid = router.get_or_create_session(user)
    result = router.delete_session(sid)
    assert result is True
    # 验证已删除
    assert router.get_session_by_platform_user(user) is None
    assert router.get_platform_user_by_session(sid) is None


def test_delete_session_nonexistent(router):
    """删除不存在的会话应返回 False。"""
    assert router.delete_session("nope_no_session_0") is False


# ============================================================================
# Section 6: SessionRouter — 边界情况
# ============================================================================


def test_many_users_same_platform(router):
    """大量同平台用户应正确处理。"""
    for i in range(50):
        user = PlatformUser(platform=PlatformType.QQ, user_id=f"bulk_{i:04d}")
        router.get_or_create_session(user)
    sessions = router.list_all_sessions()
    assert len(sessions) == 50


def test_session_id_is_stable_across_calls(router):
    """多次调用 get_or_create_session 返回相同 ID。"""
    user = PlatformUser(platform=PlatformType.SIGNAL, user_id="signal_user")
    ids = {router.get_or_create_session(user) for _ in range(10)}
    assert len(ids) == 1


def test_get_session_info(router):
    """get_session_info 应返回 SessionInfo 对象。"""
    user = PlatformUser(platform=PlatformType.HOMEASSISTANT, user_id="ha_user")
    sid = router.get_or_create_session(user)
    info = router.get_session_info(sid)
    assert info is not None
    assert isinstance(info, SessionInfo)
    assert info.session_id == sid
    assert info.platform == "homeassistant"


def test_get_session_info_nonexistent(router):
    """不存在的 session_id 应返回 None。"""
    assert router.get_session_info("ghost_session_00") is None


# ============================================================================
# Section 7: Intent — dataclass
# ============================================================================


def test_intent_to_dict():
    """Intent.to_dict() 应返回包含所有字段的字典。"""
    intent = Intent(
        category="task",
        intent_type="marketing_plan",
        confidence=0.95,
        workflow_kind="marketing_plan",
        skill_name=None,
        metadata={"matched_by": "rule"},
    )
    d = intent.to_dict()
    assert d["category"] == "task"
    assert d["intent_type"] == "marketing_plan"
    assert d["confidence"] == 0.95
    assert d["workflow_kind"] == "marketing_plan"
    assert d["skill_name"] is None
    assert d["metadata"] == {"matched_by": "rule"}


# ============================================================================
# Section 8: RouterRule — match & specificity
# ============================================================================


def test_rule_match_pattern_with_slash_prefix():
    """以 / 开头的 pattern 应使用前缀匹配。"""
    rule = RouterRule(category="task", intent_type="task_new", confidence=0.99, pattern="/task new")
    assert rule.match("/task new 推广计划") is True
    assert rule.match("/task new") is True
    assert rule.match("/TASK NEW hello") is True  # case insensitive
    assert rule.match("help me task new") is False


def test_rule_match_pattern_substring():
    """不以 / 开头的 pattern 应使用子串匹配。"""
    rule = RouterRule(category="skill", intent_type="dreamina_image", confidence=0.97, pattern="生成图片")
    assert rule.match("帮我生成图片") is True
    assert rule.match("生成图片") is True
    assert rule.match("今天天气不错") is False


def test_rule_match_keywords():
    """keywords 应使用子串匹配。"""
    rule = RouterRule(
        category="task",
        intent_type="marketing_plan",
        confidence=0.79,
        keywords=["营销计划", "推广计划"],
    )
    assert rule.match("我需要做一份营销计划") is True
    assert rule.match("推广计划下周开始") is True
    assert rule.match("今天天气如何") is False


def test_rule_match_no_pattern_no_keywords():
    """无 pattern 无 keywords 的 rule 应始终不匹配。"""
    rule = RouterRule(category="task", intent_type="general", confidence=0.5)
    assert rule.match("any message") is False


def test_rule_specificity_pattern():
    """有 pattern 时 specificity 返回 pattern 长度。"""
    rule = RouterRule(category="task", intent_type="x", confidence=0.5, pattern="/task intake marketing_plan")
    assert rule.specificity == len("/task intake marketing_plan")


def test_rule_specificity_keywords():
    """有 keywords 时 specificity 返回最长 keyword 长度。"""
    rule = RouterRule(
        category="skill",
        intent_type="x",
        confidence=0.5,
        keywords=["画一张", "做一张图"],
    )
    assert rule.specificity == 4  # len("做一张图")


def test_rule_specificity_empty_keywords():
    """keywords 为空列表时 specificity 返回 0。"""
    rule = RouterRule(category="task", intent_type="x", confidence=0.5, keywords=[])
    assert rule.specificity == 0


# ============================================================================
# Section 9: Helper functions
# ============================================================================


def test_normalize():
    """_normalize 应去除多余空白并转小写。"""
    assert _normalize("  Hello   World  ") == "hello world"
    assert _normalize("\t\nmultiple\nlines\t") == "multiple lines"
    assert _normalize("中文  测试") == "中文 测试"


def test_parse_json_payload_clean_json():
    """_parse_json_payload 应解析干净的 JSON。"""
    result = _parse_json_payload('{"category": "task"}')
    assert result == {"category": "task"}


def test_parse_json_payload_code_block():
    """_parse_json_payload 应提取 code block 中的 JSON。"""
    result = _parse_json_payload('```json\n{"category": "task"}\n```')
    assert result == {"category": "task"}


def test_parse_json_payload_json_in_text():
    """_parse_json_payload 应提取文本中的 JSON。"""
    result = _parse_json_payload('Here is the result: {"category": "skill"} done.')
    assert result == {"category": "skill"}


def test_parse_json_payload_invalid_json():
    """_parse_json_payload 对无效 JSON 应返回 None。"""
    assert _parse_json_payload("not json at all") is None
    assert _parse_json_payload('{"broken": }') is None


def test_parse_json_payload_non_dict():
    """_parse_json_payload 对非 dict JSON 应返回 None。"""
    assert _parse_json_payload("[1, 2, 3]") is None
    assert _parse_json_payload('"just a string"') is None


def test_extract_prompt_from_message_command_prefix():
    """_extract_prompt_from_message 应去除命令前缀。"""
    result = _extract_prompt_from_message("生成图片 一只猫在屋顶", "生成图片", "dreamina_image")
    assert result == "一只猫在屋顶"


def test_extract_prompt_from_message_polite_prefix():
    """_extract_prompt_from_message 应去除礼貌用语前缀。"""
    result = _extract_prompt_from_message("帮我做一张图 海报风格", "做一张图", "dreamina_image")
    assert result == "海报风格"


def test_extract_prompt_from_message_dreamina_replacements():
    """_extract_prompt_from_message 应替换 dreamina 动作短语。"""
    result = _extract_prompt_from_message("生成图片 画一张风景", "生成图片", "dreamina_image")
    assert "画一张" not in result


def test_extract_prompt_from_message_no_change():
    """_extract_prompt_from_message 对不匹配的消息应返回原文。"""
    result = _extract_prompt_from_message("今天天气怎么样", "生成图片", "dreamina_image")
    assert result == "今天天气怎么样"


# ============================================================================
# Section 10: IntentRouter — init & config loading
# ============================================================================


def test_intent_router_from_yaml(tmp_path):
    """IntentRouter.from_yaml 应正确加载配置文件。"""
    config_path = Path("/Users/dianchi/JW-Bot/astrbot/core/router_config.yaml")
    if config_path.exists():
        router = IntentRouter.from_yaml(config_path)
        assert isinstance(router, IntentRouter)
        assert len(router.task_rules) > 0
        assert len(router.skill_rules) > 0


def test_intent_router_from_dict():
    """IntentRouter 应从字典正确初始化。"""
    config = {
        "fallback_threshold": 0.8,
        "task_intents": [
            {"pattern": "/task new", "confidence": 0.99, "category": "task", "intent_type": "task_new"},
        ],
        "skill_intents": [
            {"pattern": "画图", "confidence": 0.9, "category": "skill", "intent_type": "draw"},
        ],
    }
    router = IntentRouter(config)
    assert router.fallback_threshold == 0.8
    assert len(router.task_rules) == 1
    assert len(router.skill_rules) == 1
    assert router.llm_provider is None


def test_intent_router_with_llm_provider():
    """IntentRouter 应接受 llm_provider。"""
    llm = AsyncMock()
    config = {"task_intents": [], "skill_intents": []}
    router = IntentRouter(config, llm_provider=llm)
    assert router.llm_provider is llm


def test_intent_router_default_threshold():
    """未指定 threshold 时应默认为 0.75。"""
    router = IntentRouter({"task_intents": [], "skill_intents": []})
    assert router.fallback_threshold == 0.75


# ============================================================================
# Section 11: IntentRouter — classify (rule matching)
# ============================================================================


@pytest.fixture
def intent_router():
    """使用实际配置文件创建 IntentRouter。"""
    config_path = Path("/Users/dianchi/JW-Bot/astrbot/core/router_config.yaml")
    return IntentRouter.from_yaml(config_path)


@pytest.mark.asyncio
async def test_classify_task_new(intent_router):
    """/task new 应识别为 task_new。"""
    intent = await intent_router.classify("/task new", {})
    assert intent.category == "task"
    assert intent.intent_type == "task_new"
    assert intent.confidence >= 0.99


@pytest.mark.asyncio
async def test_classify_task_intake_marketing_plan(intent_router):
    """/task intake marketing_plan 应映射到 workflow_kind。"""
    intent = await intent_router.classify("/task intake marketing_plan 做一份 Q3 营销计划", {})
    assert intent.category == "task"
    assert intent.intent_type == "marketing_plan"
    assert intent.workflow_kind == "marketing_plan"


@pytest.mark.asyncio
async def test_classify_task_ls(intent_router):
    """/task ls 等管理命令不再有 Router 规则——由 star handler 拦截，Router 返回 conversation。"""
    intent = await intent_router.classify("/task ls", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_task_show(intent_router):
    """/task show 由 star handler 处理，Router 不分类。"""
    intent = await intent_router.classify("/task show abc123", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_task_start(intent_router):
    """/task start 由 star handler 处理，Router 不分类。"""
    intent = await intent_router.classify("/task start xyz", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_task_done(intent_router):
    """/task done 由 star handler 处理，Router 不分类。"""
    intent = await intent_router.classify("/task done xyz", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_task_fail(intent_router):
    """/task fail 由 star handler 处理，Router 不分类。"""
    intent = await intent_router.classify("/task fail xyz", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_task_approve(intent_router):
    """/task approve 由 star handler 处理，Router 不分类。"""
    intent = await intent_router.classify("/task approve xyz", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_task_reject(intent_router):
    """/task reject 由 star handler 处理，Router 不分类。"""
    intent = await intent_router.classify("/task reject xyz", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_dreamina_image(intent_router):
    """包含"生成图片"应识别 dreamina_image。"""
    intent = await intent_router.classify("帮我生成图片，一只猫", {})
    assert intent.category == "skill"
    assert intent.intent_type == "dreamina_image"
    assert intent.skill_name == "dreamina_plugin"


@pytest.mark.asyncio
async def test_classify_dreamina_video(intent_router):
    """包含"生成视频"应识别 dreamina_video。"""
    intent = await intent_router.classify("生成视频，日落场景", {})
    assert intent.intent_type == "dreamina_video"


@pytest.mark.asyncio
async def test_classify_dreamina_image2video(intent_router):
    """包含"图片转视频"应识别 dreamina_image2video。"""
    intent = await intent_router.classify("图片转视频，这张照片", {})
    assert intent.intent_type == "dreamina_image2video"


@pytest.mark.asyncio
async def test_classify_dreamina_credit(intent_router):
    """包含"即梦余额"应识别 dreamina_credit。"""
    intent = await intent_router.classify("即梦余额", {})
    assert intent.intent_type == "dreamina_credit"


@pytest.mark.asyncio
async def test_classify_github(intent_router):
    """包含"GitHub"关键词应识别 github skill。"""
    intent = await intent_router.classify("帮我看看这个 github issue", {})
    assert intent.category == "skill"
    assert intent.intent_type == "github"


@pytest.mark.asyncio
async def test_classify_google_workspace(intent_router):
    """包含"google docs"应识别 google_workspace skill。"""
    intent = await intent_router.classify("打开 google docs 查看文档", {})
    assert intent.intent_type == "google_workspace"


@pytest.mark.asyncio
async def test_classify_find_nearby(intent_router):
    """包含"附近餐厅"应识别 find_nearby skill。"""
    intent = await intent_router.classify("附近餐厅推荐", {})
    assert intent.intent_type == "find_nearby"


@pytest.mark.asyncio
async def test_classify_arxiv(intent_router):
    """包含"arxiv"应识别 arxiv skill。"""
    intent = await intent_router.classify("arxiv 论文检索 transformer", {})
    assert intent.intent_type == "arxiv"


@pytest.mark.asyncio
async def test_classify_keyword_marketing_plan(intent_router):
    """关键词"营销计划"应识别 marketing_plan。"""
    intent = await intent_router.classify("我需要做一份营销计划", {})
    assert intent.intent_type == "marketing_plan"
    assert intent.workflow_kind == "marketing_plan"


@pytest.mark.asyncio
async def test_classify_keyword_content_delivery(intent_router):
    """关键词"内容交付"应识别 content_delivery。"""
    intent = await intent_router.classify("内容交付截止日期是什么", {})
    assert intent.intent_type == "content_delivery"


@pytest.mark.asyncio
async def test_classify_keyword_project_followup(intent_router):
    """关键词"项目跟进"应识别 project_followup。"""
    intent = await intent_router.classify("项目跟进情况怎么样", {})
    assert intent.intent_type == "project_followup"


@pytest.mark.asyncio
async def test_classify_keyword_approval(intent_router):
    """关键词"审批"应识别 approval_request。"""
    intent = await intent_router.classify("这个需要审批", {})
    assert intent.intent_type == "approval_request"


# ============================================================================
# Section 12: IntentRouter — classify (edge cases & fallback)
# ============================================================================


@pytest.mark.asyncio
async def test_classify_empty_message(intent_router):
    """空消息应返回默认 conversation intent。"""
    intent = await intent_router.classify("", {})
    assert intent.category == "conversation"
    assert intent.intent_type == "general"
    assert intent.confidence == 0.4


@pytest.mark.asyncio
async def test_classify_whitespace_message(intent_router):
    """纯空白消息应返回默认 conversation intent。"""
    intent = await intent_router.classify("   \n\t  ", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_classify_no_match_returns_default(intent_router):
    """不匹配任何规则且无 LLM 时应返回默认 intent。"""
    router = IntentRouter({"task_intents": [], "skill_intents": []})
    intent = await router.classify("random message", {})
    assert intent.category == "conversation"
    assert intent.confidence == 0.4


@pytest.mark.asyncio
async def test_classify_rule_below_threshold(intent_router):
    """规则匹配但 confidence 低于 threshold 且无 LLM 时仍返回规则匹配。"""
    intent = await intent_router.classify("营销计划", {})
    # marketing_plan keyword confidence = 0.79 > 0.75 threshold
    assert intent.intent_type == "marketing_plan"


@pytest.mark.asyncio
async def test_llm_fallback_when_no_rule_matches():
    """无规则匹配且有 LLM provider 时应调用 LLM。"""
    async def mock_llm(system, prompt, context):
        return '{"category": "task", "intent_type": "marketing_plan", "confidence": 0.7, "workflow_kind": "marketing_plan"}'

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "You are a classifier"},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("请做一份推广方案", {})
    assert intent.category == "task"
    assert intent.intent_type == "marketing_plan"


@pytest.mark.asyncio
async def test_llm_fallback_code_block_json():
    """LLM 返回 code block JSON 时应正确解析。"""
    async def mock_llm(system, prompt, context):
        return '```json\n{"category": "skill", "intent_type": "dreamina_image", "confidence": 0.72}\n```'

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "classify"},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("画一只鸟", {})
    assert intent.category == "skill"
    assert intent.intent_type == "dreamina_image"


@pytest.mark.asyncio
async def test_llm_returns_invalid_json():
    """LLM 返回无效 JSON 时应返回默认 intent。"""
    async def mock_llm(system, prompt, context):
        return "this is not json at all"

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "classify"},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("hello world", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_llm_returns_none():
    """LLM 返回 None 时应跳过 LLM 分支。"""
    async def mock_llm(system, prompt, context):
        return None

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "classify"},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("hello", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_llm_no_system_prompt():
    """无 system_prompt 时应跳过 LLM 分支。"""
    async def mock_llm(system, prompt, context):
        return '{"category": "task"}'

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": ""},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("hello", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_llm_returns_array():
    """LLM 返回数组而非对象时应返回 None。"""
    async def mock_llm(system, prompt, context):
        return '[1, 2, 3]'

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "classify"},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("hello", {})
    assert intent.category == "conversation"


@pytest.mark.asyncio
async def test_llm_beats_rule_when_higher_confidence():
    """LLM 返回的 confidence 高于规则时优先 LLM。"""
    async def mock_llm(system, prompt, context):
        return '{"category": "skill", "intent_type": "custom", "confidence": 0.95}'

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "classify"},
        "fallback_threshold": 0.99,
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("something", {})
    assert intent.category == "skill"
    assert intent.confidence == 0.95


@pytest.mark.asyncio
async def test_rule_beats_llm_when_higher_confidence():
    """规则 confidence 高于 LLM 时优先规则。"""
    async def mock_llm(system, prompt, context):
        return '{"category": "skill", "intent_type": "custom", "confidence": 0.5}'

    config = {
        "task_intents": [
            {"pattern": "/task new", "confidence": 0.99, "category": "task", "intent_type": "task_new"},
        ],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "classify"},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("/task new", {})
    # Rule matches at 0.99, LLM returns 0.5, so rule wins
    assert intent.intent_type == "task_new"


# ============================================================================
# Section 13: IntentRouter — transport metadata
# ============================================================================


@pytest.mark.asyncio
async def test_transport_metadata_qqbot(intent_router):
    """context 含 platform_id=qqbot 时应设置 metadata["platform"]。"""
    intent = await intent_router.classify("/task new", {"platform_id": "qqbot"})
    assert intent.metadata.get("platform") == "qqbot"


@pytest.mark.asyncio
async def test_transport_metadata_hermes_bridge(intent_router):
    """context 含 session_key 时应设置 transport=hermes_bridge。"""
    intent = await intent_router.classify("/task new", {"session_key": "sk_123"})
    assert intent.metadata.get("transport") == "hermes_bridge"
    assert intent.metadata.get("session_key") == "sk_123"


@pytest.mark.asyncio
async def test_transport_metadata_webhook_event(intent_router):
    """context 含 webhook_event 时应透传。"""
    intent = await intent_router.classify("/task new", {"webhook_event": "message.created"})
    assert intent.metadata.get("webhook_event") == "message.created"


@pytest.mark.asyncio
async def test_llm_metadata_includes_transport(intent_router):
    """LLM 分类结果也应包含 transport metadata。"""
    async def mock_llm(system, prompt, context):
        return '{"category": "task", "intent_type": "custom", "confidence": 0.8}'

    config = {
        "task_intents": [],
        "skill_intents": [],
        "llm_fallback": {"system_prompt": "classify"},
    }
    router = IntentRouter(config, llm_provider=mock_llm)
    intent = await router.classify("hello", {"platform_id": "qqbot", "webhook_event": "test"})
    assert intent.metadata.get("platform") == "qqbot"
    assert intent.metadata.get("matched_by") == "llm"


# ============================================================================
# Section 14: IntentRouter — command extraction
# ============================================================================


@pytest.mark.asyncio
async def test_rule_with_command_name_synthetic_command(intent_router):
    """匹配 rule 且有 command_name 时应生成 synthetic_command。"""
    intent = await intent_router.classify("生成图片 一只猫在屋顶", {})
    assert "synthetic_command" in intent.metadata
    assert "synthetic_prompt" in intent.metadata


@pytest.mark.asyncio
async def test_metadata_matched_by_rule(intent_router):
    """规则匹配时 matched_by 应为 "rule"。"""
    intent = await intent_router.classify("/task new", {})
    assert intent.metadata.get("matched_by") == "rule"


# ============================================================================
# Section 15: IntentRouter — activated_handler_count
# ============================================================================


@pytest.mark.asyncio
async def test_default_intent_includes_activated_handler_count(intent_router):
    """空消息且 context 含 activated_handler_count 时应透传。"""
    intent = await intent_router.classify("", {"activated_handler_count": 5})
    assert intent.metadata.get("activated_handler_count") == 5
