
"""
营销团队集成工具 + OpenCLI 集成插件
结合 OpenCLI 的强大搜索能力和营销团队集成工具的专业营销能力
"""

import logging
import os
import subprocess
from pathlib import Path

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter

from data.plugins._shared_marketing_legacy import build_marketing_legacy_response
from jw_claw.astrbot import (
    HarnessAstrBotBridge,
    AstrBotLLMAdapter,
    is_astrbot_provider_bridge_enabled,
)
from data.plugins._shared_harness_bridge import get_harness_or_legacy_text

logger = logging.getLogger("openclaw.plugins.marketing_opencli")

def _env_with_node_path() -> dict:
    env = os.environ.copy()
    extra_dirs = ["/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin",
                  str(Path.home() / ".local" / "bin")]
    extra = ":".join(d for d in extra_dirs if d not in env.get("PATH", ""))
    if extra:
        env["PATH"] = extra + ":" + env.get("PATH", "")
    return env


def check_opencli_installed():
    """检查 OpenCLI 是否已安装"""
    try:
        result = subprocess.run(
            ["opencli", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            env=_env_with_node_path(),
        )
        return result.returncode == 0
    except Exception:
        return False


@star.register(
    "marketing_opencli",
    "营销+OpenCLI集成工具",
    "结合OpenCLI搜索能力和营销工具的专业营销能力",
    "1.0.0"
)
class MarketingOpenCLIPlugin(star.Star):
    def __init__(self, context):
        super().__init__(context)
        self.harness_bridge = HarnessAstrBotBridge()
        if is_astrbot_provider_bridge_enabled():
            adapter = AstrBotLLMAdapter(context)
            if adapter.available():
                self.harness_bridge.set_llm_client(adapter)
        logger.info("营销+OpenCLI集成工具加载成功")
        if not check_opencli_installed():
            logger.info("OpenCLI未安装，模板模式运行中（安装后可启用实时搜索）")

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
            "mtoc_hot": "🎯 热点营销策划",
            "mtoc_competitor": "🏢 竞品分析报告",
            "mtoc_news": "📰 新闻营销方案",
            "mtoc_data": "📊 数据收集与分析报告",
        }
        return build_marketing_legacy_response(
            command_name,
            prompt,
            titles,
            "营销分析结果",
            inline_title=True,
        )

    @filter.command("mtoc_help")
    async def marketing_opencli_help(self, event: AstrMessageEvent):
        help_text = """🚀 营销+OpenCLI集成工具 - 帮助

📢 热点营销策划
/mtoc_hot [topic] - 基于热点话题的营销策划

🏢 竞品分析
/mtoc_competitor [brand] - 竞品分析与对策

📰 新闻营销
/mtoc_news [keyword] - 基于新闻的营销方案

📊 数据收集与分析
/mtoc_data [topic] - 数据收集与分析报告

🎯 组合使用示例
1. /mtoc_hot AI人工智能 - 基于AI热点的营销方案
2. /mtoc_competitor 小米 - 小米竞品分析
3. /mtoc_news 新能源汽车 - 基于新能源新闻的营销
4. /mtoc_data 直播电商 - 直播电商数据收集与分析

单独使用工具
- /mt_* - 营销工具
- /ocli_* - OpenCLI工具

查看更多
/mtoc_about - 关于此工具"""
        yield event.plain_result(help_text)

    @filter.command("mtoc_about")
    async def marketing_opencli_about(self, event: AstrMessageEvent):
        about_text = """🎯 营销+OpenCLI集成工具 v1.0.0

什么是营销+OpenCLI集成?
结合 OpenCLI 的强大搜索能力（430+命令，70+网站）和营销团队集成工具的专业营销能力，打造超级营销助手！

核心能力
🔍 数据收集
- 热点话题搜索（Hacker News, Google News）
- 竞品信息收集（Wikipedia, Google）
- 行业新闻追踪
- 市场数据获取

📊 数据分析
- 热点趋势分析
- 竞品对比分析
- 新闻营销洞察
- 数据报告生成

🎨 营销策划
- 热点营销方案
- 竞品应对策略
- 新闻营销文案
- 数据驱动决策

使用流程
1. 数据收集 → OpenCLI自动搜索
2. 数据分析 → 智能分析洞察
3. 营销方案 → 专业营销输出

基于 OpenCLI + 营销团队集成工具！"""
        yield event.plain_result(about_text)

    @filter.command("mtoc_hot")
    async def hot_topic_marketing(self, event: AstrMessageEvent, topic: str = None):
        if not topic:
            guide_text = """📢 热点营销策划助手

使用方式:
/mtoc_hot [热点话题]

示例:
1. /mtoc_hot AI人工智能
2. /mtoc_hot 元宇宙
3. /mtoc_hot 新能源汽车

工作流程:
1. 搜索热门话题 (Hacker News, Google News)
2. 分析热点趋势
3. 生成热点营销方案"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mtoc_hot", topic):
            yield result

    @filter.command("mtoc_competitor")
    async def competitor_analysis(self, event: AstrMessageEvent, brand: str = None):
        if not brand:
            guide_text = """🏢 竞品分析助手

使用方式:
/mtoc_competitor [品牌名]

示例:
1. /mtoc_competitor 小米
2. /mtoc_competitor 耐克
3. /mtoc_competitor 星巴克

工作流程:
1. 搜索竞品信息 (Wikipedia, Google)
2. 分析竞品优劣势
3. 生成竞品应对策略"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mtoc_competitor", brand):
            yield result

    @filter.command("mtoc_news")
    async def news_marketing(self, event: AstrMessageEvent, keyword: str = None):
        if not keyword:
            guide_text = """📰 新闻营销助手

使用方式:
/mtoc_news [关键词]

示例:
1. /mtoc_news 新能源汽车
2. /mtoc_news 人工智能
3. /mtoc_news 健康生活

工作流程:
1. 搜索行业新闻 (Google News, Reuters)
2. 分析新闻热点
3. 生成新闻营销文案"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mtoc_news", keyword):
            yield result

    @filter.command("mtoc_data")
    async def data_collection_analysis(self, event: AstrMessageEvent, topic: str = None):
        if not topic:
            guide_text = """📊 数据收集与分析助手

使用方式:
/mtoc_data [主题]

示例:
1. /mtoc_data 直播电商
2. /mtoc_data 智能家居
3. /mtoc_data 在线教育

工作流程:
1. 收集市场数据 (多源搜索)
2. 整理分析数据
3. 生成数据分析报告"""
            yield event.plain_result(guide_text)
            return
        async for result in self._run_harness_command(event, "mtoc_data", topic):
            yield result

    @filter.command("mtoc_demo")
    async def marketing_opencli_demo(self, event: AstrMessageEvent):
        demo_text = """🎯 营销+OpenCLI集成工具 - 演示

所有功能已就绪！

📢 热点营销 - /mtoc_hot
🏢 竞品分析 - /mtoc_competitor
📰 新闻营销 - /mtoc_news
📊 数据分析 - /mtoc_data

快速开始:
1. /mtoc_hot AI人工智能 - 基于AI热点的营销方案
2. /mtoc_competitor 小米 - 小米竞品分析
3. /mtoc_news 新能源汽车 - 基于新能源新闻的营销
4. /mtoc_data 直播电商 - 直播电商数据收集与分析

查看帮助: /mtoc_help
查看关于: /mtoc_about"""
        yield event.plain_result(demo_text)
