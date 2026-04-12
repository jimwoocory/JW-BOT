"""
OpenCLI AstrBot 插件
集成 OpenCLI 命令到 AstrBot
"""

import logging
import os
import subprocess
from pathlib import Path

# Ensure Homebrew + local bin are in PATH so 'opencli' (node script) is found
_EXTRA_BINS = [
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    str(Path.home() / ".local" / "bin"),
]

logger = logging.getLogger("openclaw.plugins.opencli")

def _env_with_node_path() -> dict:
    env = os.environ.copy()
    current = env.get("PATH", "")
    extra = ":".join(d for d in _EXTRA_BINS if d not in current)
    if extra:
        env["PATH"] = extra + ":" + current
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


def run_opencli_command(command, timeout=30):
    """运行 OpenCLI 命令"""
    try:
        result = subprocess.run(
            ["opencli"] + command.split(),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_env_with_node_path(),
        )
        if result.returncode == 0:
            return {"success": True, "output": result.stdout}
        else:
            return {"success": False, "error": result.stderr or result.stdout}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter


@star.register("opencli", "OpenClaw Team", "OpenCLI 集成插件 - 430+ 命令支持", "1.0.0")
class OpenCLIPlugin(star.Star):
    def __init__(self, context):
        super().__init__(context)
        self.opencli_installed = check_opencli_installed()
        if self.opencli_installed:
            logger.info("OpenCLI 插件加载成功")
        else:
            logger.info("OpenCLI 未安装，请运行: npm install -g @jackwener/opencli")

    @filter.command("ocli_help")
    async def opencli_help(self, event: AstrMessageEvent):
        help_text = "OpenCLI 命令帮助\n\n快捷命令\n/ocli_list - 列出所有 OpenCLI 命令\n/ocli_hn [limit] - 查看 Hacker News 热门\n/ocli_google [query] - Google 搜索\n/ocli_wiki [query] - Wikipedia 搜索\n/ocli_news [limit] - 查看 Google News\n/ocli_imdb_top - 查看 IMDb Top 250\n/ocli_spotify_play [query] - 播放 Spotify\n/ocli_spotify_status - 查看 Spotify 状态\n\n通用命令\n/ocli [command] - 执行任意 OpenCLI 命令\n\n更多信息\n/ocli_about - 关于 OpenCLI"
        yield event.plain_result(help_text)

    @filter.command("ocli_about")
    async def opencli_about(self, event: AstrMessageEvent):
        about_text = "OpenCLI v1.6.7\n\n什么是 OpenCLI?\nMake any website, Electron App, or Local Tool your CLI.\n一个可以将任何网站、Electron 应用或本地工具转换为 CLI 的工具。\n\n核心特性\n- 430+ 内置命令\n- 覆盖 70+ 网站\n- 公共 API 命令（无需登录）\n- Cookie/浏览器命令（需登录）\n- 专为 AI Agent 设计\n- 零 LLM 成本运行时\n- 确定性输出\n\n支持的网站（公共 API）\n- Hacker News, Google, Wikipedia, IMDb\n- Stack Overflow, Spotify, Steam\n- Product Hunt, Reuters, Lobste.rs\n- 等等...\n\n更多信息: https://github.com/jackwener/opencli"
        yield event.plain_result(about_text)

    @filter.command("ocli_list")
    async def opencli_list(self, event: AstrMessageEvent):
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("获取 OpenCLI 命令列表...")
        result = run_opencli_command("list")
        if result["success"]:
            output = result["output"]
            if len(output) > 2000:
                output = output[:2000] + "\n\n... (输出过长，已截断)\n使用 /ocli [command] 执行特定命令"
            yield event.plain_result(output)
        else:
            yield event.plain_result("错误: 获取命令列表失败: " + result.get("error", "未知错误"))

    @filter.command("ocli")
    async def opencli_exec(self, event: AstrMessageEvent):
        command = event.message_str.strip()
        if not command:
            yield event.plain_result("请指定 OpenCLI 命令，例如: /ocli hackernews top --limit 5")
            return
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("执行 OpenCLI 命令: " + command)
        result = run_opencli_command(command)
        if result["success"]:
            output = result["output"]
            if len(output) > 3000:
                output = output[:3000] + "\n\n... (输出过长，已截断)"
            yield event.plain_result(output)
        else:
            yield event.plain_result("错误: 命令执行失败: " + result.get("error", "未知错误"))

    @filter.command("ocli_hn")
    async def opencli_hackernews(self, event: AstrMessageEvent):
        limit = event.message_str.strip() or "5"
        if not limit.isdigit():
            limit = "5"
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("获取 Hacker News 热门话题 (" + limit + "条)...")
        result = run_opencli_command("hackernews top --limit " + limit)
        if result["success"]:
            yield event.plain_result(result["output"])
        else:
            yield event.plain_result("错误: 获取失败: " + result.get("error", "未知错误"))

    @filter.command("ocli_google")
    async def opencli_google(self, event: AstrMessageEvent):
        query = event.message_str.strip()
        if not query:
            yield event.plain_result("请指定搜索关键词，例如: /ocli_google AI")
            return
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("Google 搜索: " + query)
        result = run_opencli_command("google search " + query)
        if result["success"]:
            output = result["output"]
            if len(output) > 2000:
                output = output[:2000] + "\n\n... (输出过长，已截断)"
            yield event.plain_result(output)
        else:
            yield event.plain_result("错误: 搜索失败: " + result.get("error", "未知错误"))

    @filter.command("ocli_wiki")
    async def opencli_wikipedia(self, event: AstrMessageEvent):
        query = event.message_str.strip()
        if not query:
            yield event.plain_result("请指定搜索关键词，例如: /ocli_wiki Python")
            return
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("Wikipedia 搜索: " + query)
        result = run_opencli_command("wikipedia search " + query)
        if result["success"]:
            output = result["output"]
            if len(output) > 2000:
                output = output[:2000] + "\n\n... (输出过长，已截断)"
            yield event.plain_result(output)
        else:
            yield event.plain_result("错误: 搜索失败: " + result.get("error", "未知错误"))

    @filter.command("ocli_news")
    async def opencli_news(self, event: AstrMessageEvent):
        limit = event.message_str.strip() or "3"
        if not limit.isdigit():
            limit = "3"
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("获取 Google News 头条 (" + limit + "条)...")
        result = run_opencli_command("google news --limit " + limit)
        if result["success"]:
            yield event.plain_result(result["output"])
        else:
            yield event.plain_result("错误: 获取失败: " + result.get("error", "未知错误"))

    @filter.command("ocli_imdb_top")
    async def opencli_imdb_top(self, event: AstrMessageEvent):
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("获取 IMDb Top 250...")
        result = run_opencli_command("imdb top")
        if result["success"]:
            output = result["output"]
            if len(output) > 2000:
                output = output[:2000] + "\n\n... (输出过长，已截断)"
            yield event.plain_result(output)
        else:
            yield event.plain_result("错误: 获取失败: " + result.get("error", "未知错误"))

    @filter.command("ocli_spotify_play")
    async def opencli_spotify_play(self, event: AstrMessageEvent):
        query = event.message_str.strip()
        if not query:
            yield event.plain_result("请指定搜索关键词，例如: /ocli_spotify_play Imagine Dragons")
            return
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("Spotify 播放: " + query)
        result = run_opencli_command("spotify play --query " + query)
        if result["success"]:
            yield event.plain_result(result["output"])
        else:
            yield event.plain_result("错误: 播放失败: " + result.get("error", "未知错误"))

    @filter.command("ocli_spotify_status")
    async def opencli_spotify_status(self, event: AstrMessageEvent):
        if not self.opencli_installed:
            yield event.plain_result("警告: OpenCLI 未安装，请先运行: npm install -g @jackwener/opencli")
            return
        yield event.plain_result("获取 Spotify 播放状态...")
        result = run_opencli_command("spotify status")
        if result["success"]:
            yield event.plain_result(result["output"])
        else:
            yield event.plain_result("错误: 获取失败: " + result.get("error", "未知错误"))
