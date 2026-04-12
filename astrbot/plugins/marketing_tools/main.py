
import logging

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from data.plugins._shared_marketing_legacy import build_marketing_legacy_response
from jw_claw.astrbot import (
    HarnessAstrBotBridge,
    AstrBotLLMAdapter,
    is_astrbot_provider_bridge_enabled,
)
from data.plugins._shared_harness_bridge import get_harness_or_legacy_text

logger = logging.getLogger("openclaw.plugins.marketing_tools")


@star.register(
    "marketing_tools",
    "推广团队集成工具",
    "专门为公司推广团队打造的AI助手工具集",
    "1.0.0"
)
class MarketingToolsPlugin(star.Star):
    def __init__(self, context):
        super().__init__(context)
        self.harness_bridge = HarnessAstrBotBridge()
        if is_astrbot_provider_bridge_enabled():
            adapter = AstrBotLLMAdapter(context)
            if adapter.available():
                self.harness_bridge.set_llm_client(adapter)
        logger.info("推广团队集成工具加载成功")

    async def _run_harness_command(self, event: AstrMessageEvent, command_name: str, prompt: str):
        response_text = await get_harness_or_legacy_text(
            self.harness_bridge,
            command_name,
            prompt,
            event,
            self._build_legacy_response,
        )
        yield event.plain_result(response_text)

    def _build_legacy_response(self, command_name: str, prompt: str) -> str:
        titles = {
            "mt_marketing": "🎯 品牌营销策划需求已接收",
            "mt_copy": "✍️ 创意文案需求已接收",
            "mt_event": "🎉 活动策划需求已接收",
            "mt_pr": "📢 公关管理需求已接收",
            "mt_analytics": "📊 数据分析需求已接收",
        }
        return build_marketing_legacy_response(
            command_name,
            prompt,
            titles,
            "营销需求已接收",
        )

    @filter.command("mt_help")
    async def marketing_help(self, event: AstrMessageEvent):
        help_text = """🎉 推广团队集成工具 - 帮助

📢 品牌营销策划
/mt_marketing - 品牌营销策划助手

✍️ 创意文案
/mt_copy - 创意文案生成

🎉 活动策划
/mt_event - 活动策划助手

📢 公关管理
/mt_pr - 公关管理助手

📊 数据分析
/mt_analytics - 数据分析助手

使用示例：
1. /mt_marketing 为我们的新产品制定推广方案
2. /mt_copy 写一篇微信公众号推广文案
3. /mt_event 策划一场产品发布会
4. /mt_pr 撰写一篇新闻稿
5. /mt_analytics 分析上月推广数据

更多详情：/mt_about"""
        yield event.plain_result(help_text)

    @filter.command("mt_about")
    async def marketing_about(self, event: AstrMessageEvent):
        about_text = """🚀 推广团队集成工具 v1.0.0

专为公司推广团队打造的AI助手工具集，集成：

1️⃣ 品牌营销策划
   - 品牌战略规划
   - 推广渠道规划
   - 内容营销策划
   - KOL/网红合作
   - 营销活动策划

2️⃣ 创意文案
   - 品牌故事创作
   - 社交媒体文案
   - 营销文案
   - 产品描述
   - 广告文案

3️⃣ 活动策划
   - 活动策划
   - 路演策划
   - 产品发布会
   - 展览策划
   - 预算管理

4️⃣ 公关管理
   - 媒体关系管理
   - 新闻稿撰写
   - 危机公关
   - 品牌声誉管理
   - 采访准备

5️⃣ 数据分析
   - KPI体系设计
   - 数据分析
   - 效果评估
   - ROI计算
   - 报告撰写

基于专业的营销方法论和最佳实践！"""
        yield event.plain_result(about_text)

    @filter.command("mt_marketing")
    async def marketing_planner(self, event: AstrMessageEvent, prompt: str = None):
        if not prompt:
            guide_text = """📢 品牌营销策划助手

使用方式：
/mt_marketing [你的需求]

示例：
1. /mt_marketing 为我们的新AI产品制定季度推广方案
2. /mt_marketing 制定小红书推广策略，目标用户是年轻女性
3. /mt_marketing 规划月度内容日历，重点是双11活动

请描述你的具体需求，包括：
- 品牌/产品信息
- 推广目标
- 目标受众
- 预算范围
- 推广周期"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mt_marketing", prompt):
            yield result

    @filter.command("mt_copy")
    async def creative_copywriting(self, event: AstrMessageEvent, prompt: str = None):
        if not prompt:
            guide_text = """✍️ 创意文案助手

使用方式：
/mt_copy [你的需求]

示例：
1. /mt_copy 为我们的新产品写一篇微信公众号文章
2. /mt_copy 写一篇小红书种草文案
3. /mt_copy 创作品牌故事，展现我们的技术实力
4. /mt_copy 写一条促销活动的微博文案

请描述你的具体需求，包括：
- 平台类型（微信/微博/抖音/小红书等）
- 推广主题
- 目标受众
- 品牌调性"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mt_copy", prompt):
            yield result

    @filter.command("mt_event")
    async def event_planner(self, event: AstrMessageEvent, prompt: str = None):
        if not prompt:
            guide_text = """🎉 活动策划助手

使用方式：
/mt_event [你的需求]

示例：
1. /mt_event 策划一场新产品发布会，规模200人
2. /mt_event 规划全国路演方案，覆盖5个城市
3. /mt_event 策划年度客户答谢活动
4. /mt_event 设计一场行业峰会的执行方案

请描述你的具体需求，包括：
- 活动类型
- 活动规模
- 活动时间
- 活动地点
- 预算范围"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mt_event", prompt):
            yield result

    @filter.command("mt_pr")
    async def pr_management(self, event: AstrMessageEvent, prompt: str = None):
        if not prompt:
            guide_text = """📢 公关管理助手

使用方式：
/mt_pr [你的需求]

示例：
1. /mt_pr 撰写一篇关于我们新产品发布的新闻稿
2. /mt_pr 制定年度公关传播方案
3. /mt_pr 为CEO准备媒体采访
4. /mt_pr 处理一个危机公关事件

请描述你的具体需求，包括：
- 新闻事件/主题
- 核心信息点
- 目标媒体类型
- 发布时间要求"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mt_pr", prompt):
            yield result

    @filter.command("mt_analytics")
    async def data_analytics(self, event: AstrMessageEvent, prompt: str = None):
        if not prompt:
            guide_text = """📊 数据分析助手

使用方式：
/mt_analytics [你的需求]

示例：
1. /mt_analytics 为我们的推广项目设计KPI指标体系
2. /mt_analytics 分析上月推广数据并撰写报告
3. /mt_analytics 计算这次活动的ROI
4. /mt_analytics 设计A/B测试方案

请描述你的具体需求，包括：
- 分析周期
- 数据来源
- 分析目标
- 对比基准"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mt_analytics", prompt):
            yield result

    @filter.command("mt_demo")
    async def marketing_demo(self, event: AstrMessageEvent):
        demo_text = """🎯 推广团队集成工具 - 演示

所有功能已就绪！

📢 品牌营销策划 - /mt_marketing
✍️ 创意文案 - /mt_copy
🎉 活动策划 - /mt_event
📢 公关管理 - /mt_pr
📊 数据分析 - /mt_analytics

快速开始：
1. /mt_marketing 为我们的新服务制定推广方案
2. /mt_copy 写一篇社交媒体推广文案
3. /mt_event 策划一场客户活动
4. /mt_pr 撰写一篇新闻稿
5. /mt_analytics 分析推广效果

查看帮助：/mt_help
查看关于：/mt_about"""
        yield event.plain_result(demo_text)
