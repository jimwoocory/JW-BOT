"""
即梦 AI CLI 插件 - 让 AstrBot 可以调用即梦 CLI 进行图片和视频生成
"""

import asyncio
import subprocess
import json
import re
import os
import shlex
import tempfile
import urllib.request
from typing import Optional
from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Image
from astrbot.api.star import Star, register


@register(
    "dreamina_plugin",
    "dreamina_plugin",
    "即梦 AI CLI 插件，支持文生图、文生视频等功能",
    "0.0.2",
)
class DreaminaPlugin(Star):
    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context
        self.last_image_path: Optional[str] = None
        self.credit_threshold = 100  # 余额提醒阈值
        self.api_key_suffix = "lVJnPr"  # API key 后六位

    async def initialize(self) -> None:
        """插件初始化"""
        # 验证 dreamina CLI 是否可用
        try:
            result = subprocess.run(
                ["dreamina", "-h"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info("✅ 即梦 CLI 已安装并可用")
                # 注册定时检查任务
                await self._register_cron_check()
            else:
                logger.warning("❌ 即梦 CLI 安装异常")
        except FileNotFoundError:
            logger.error("❌ 未找到 dreamina 命令，请先安装即梦 CLI")
        except Exception as e:
            logger.error(f"❌ 即梦 CLI 验证失败：{e}")

    async def _register_cron_check(self):
        """注册定时检查余额任务"""
        try:
            # 每 6 小时检查一次余额
            await self.context.cron_manager.add_basic_job(
                name="dreamina_credit_check",
                cron_expression="0 */6 * * *",
                handler=self._scheduled_credit_check,
                description="即梦 Token 余额定时检查",
                timezone="Asia/Shanghai",
                persistent=True,
            )
            logger.info("✅ 即梦 Token 定时检查任务已注册（每 6 小时）")
        except Exception as e:
            logger.error(f"❌ 注册定时检查任务失败：{e}")

    async def _scheduled_credit_check(self):
        """定时检查余额（由 cron 触发）"""
        try:
            command = ["user_credit"]
            success, output = await self._execute_dreamina(command, timeout=30)

            if success:
                credit = None
                try:
                    json_match = re.search(r"\{[^{}]*\}", output, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group())
                        credit = data.get("credit")
                except:
                    pass

                if credit is not None:
                    if credit < self.credit_threshold:
                        logger.warning(
                            f"⚠️ 即梦 Token 余额不足！当前余额：{credit}，阈值：{self.credit_threshold}，"
                            f"API Key 后六位：{self.api_key_suffix}"
                        )
                    else:
                        logger.info(
                            f"✅ 即梦 Token 余额正常：{credit}，API Key 后六位：{self.api_key_suffix}"
                        )
        except Exception as e:
            logger.error(f"❌ 定时检查余额失败：{e}")

    async def _execute_dreamina(
        self, command: list, timeout: int = 300, _retry: int = 3
    ) -> tuple[bool, str]:
        """执行即梦 CLI 命令

        Args:
            command: 命令参数列表
            timeout: 超时时间（秒）
            _retry: ExceedConcurrencyLimit 时的最大重试次数

        Returns:
            (success, output)
        """
        for attempt in range(1, _retry + 1):
            try:
                full_command = ["dreamina"] + command
                logger.info(f"执行命令（第 {attempt} 次）：{' '.join(full_command)}")

                result = await asyncio.to_thread(
                    subprocess.run,
                    full_command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )

                output = result.stdout
                if result.stderr:
                    output += f"\n错误：{result.stderr}"

                if "ExceedConcurrencyLimit" in output and attempt < _retry:
                    wait = 10 * attempt
                    logger.warning(
                        f"触发并发限制，{wait} 秒后重试（{attempt}/{_retry}）"
                    )
                    await asyncio.sleep(wait)
                    continue

                return result.returncode == 0, output

            except subprocess.TimeoutExpired:
                return False, f"命令执行超时（{timeout}秒）"
            except Exception as e:
                return False, f"执行失败：{str(e)}"

        return False, "多次重试后仍触发并发限制，请稍后再试"

    def _check_gen_status(self, output: str) -> tuple[bool, str]:
        """检查生成任务的实际状态（CLI 返回码可能为 0 但任务本身失败）

        Returns:
            (is_success, fail_reason_or_empty)
        """
        try:
            json_match = re.search(r'\{.*"gen_status".*\}', output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                gen_status = data.get("gen_status", "")
                if gen_status == "fail":
                    fail_reason = data.get("fail_reason", "未知原因")
                    return False, fail_reason
        except Exception:
            pass
        return True, ""

    def _extract_prompt(self, message: str, intent: str = "image") -> str:
        """从自然语言消息中提取生成 prompt"""
        text = message.strip()
        text = re.sub(r"^(帮我|请|麻烦|能|可以|帮).{0,2}", "", text)
        text = re.sub(r"^(生成|画|制作|做|创作|绘制|创建|来|给我)", "", text)
        text = re.sub(r"^(一张|一幅|一个|一段|个|张|幅|段)", "", text)
        if intent == "image":
            text = re.sub(r"(图片|照片|插画|壁纸|图)$", "", text)
        elif intent == "video":
            text = re.sub(r"(视频|动画|短片|影片|动效)$", "", text)
        text = text.strip("，。！？,.!? \t")
        return text if text else message.strip()

    def _parse_submit_id(self, output: str) -> Optional[str]:
        """从输出中提取 submit_id"""
        # 尝试匹配 JSON 格式
        try:
            # 查找 JSON 部分
            json_match = re.search(r'\{[^{}]*"submit_id"[^{}]*\}', output, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("submit_id")
        except:
            pass

        # 尝试直接匹配 submit_id
        match = re.search(r'submit_id["\s:=]+([a-zA-Z0-9]+)', output)
        if match:
            return match.group(1)

        return None

    @filter.command("生成图片")
    async def text2image(self, event: AstrMessageEvent, prompt: str = ""):
        """文生图功能"""
        if not prompt:
            yield event.plain_result("请提供图片描述，例如：/生成图片 一只可爱的橘猫")
            return

        # 构建命令
        command = [
            "text2image",
            "--prompt",
            prompt,
            "--ratio",
            "1:1",
            "--resolution_type",
            "2k",
            "--poll",
        ]

        yield event.plain_result(f"正在生成图片：{prompt}\n这可能需要几分钟时间...")

        # 执行命令
        success, output = await self._execute_dreamina(command, timeout=600)

        if success:
            gen_ok, fail_reason = self._check_gen_status(output)
            if not gen_ok:
                yield event.plain_result(f"生成失败：{fail_reason}")
                return
            url_match = re.search(r'https?://[^\s<>"]+\.(?:jpg|png)[^\s<>"]*', output)
            if url_match:
                image_url = url_match.group()
                try:
                    suffix = ".png" if ".png" in image_url else ".jpg"
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    tmp.close()
                    await asyncio.to_thread(
                        urllib.request.urlretrieve, image_url, tmp.name
                    )
                    self.last_image_path = tmp.name
                    logger.info(f"图片已下载到：{tmp.name}")
                    yield event.image_result(image_url)
                    yield event.plain_result(
                        "图片已保存，可用 /图片转视频 <描述> 生成动画"
                    )
                except Exception as e:
                    logger.warning(f"图片下载失败：{e}")
                    yield event.image_result(image_url)
            else:
                yield event.plain_result(f"生成成功！\n{output[:500]}")
        else:
            yield event.plain_result(f"生成失败：{output}")

    @filter.command("生成视频")
    async def text2video(self, event: AstrMessageEvent, prompt: str = ""):
        """文生视频功能"""
        if not prompt:
            yield event.plain_result(
                "请提供视频描述，例如：/生成视频 海浪拍打礁石，慢动作"
            )
            return

        # 构建命令
        command = [
            "text2video",
            "--prompt",
            prompt,
            "--duration",
            "5",
            "--ratio",
            "16:9",
            "--video_resolution",
            "720p",
            "--poll",
        ]

        yield event.plain_result(f"正在生成视频：{prompt}\n这可能需要较长时间...")

        # 执行命令
        success, output = await self._execute_dreamina(command, timeout=900)

        if success:
            gen_ok, fail_reason = self._check_gen_status(output)
            if not gen_ok:
                yield event.plain_result(f"生成失败：{fail_reason}")
                return
            url_match = re.search(r'https?://[^\s<>"]+\.mp4[^\s<>"]*', output)
            if url_match:
                yield event.plain_result(f"视频生成成功：{url_match.group()}")
            else:
                yield event.plain_result(f"生成成功！\n{output[:500]}")
        else:
            yield event.plain_result(f"生成失败：{output}")

    @filter.command("图片转视频")
    async def image2video(self, event: AstrMessageEvent, prompt: str = ""):
        """将最近生成的图片动画化为视频"""
        if not self.last_image_path or not os.path.exists(self.last_image_path):
            yield event.plain_result(
                "没有找到最近生成的图片，请先用 /生成图片 生成一张图片"
            )
            return

        command = [
            "image2video",
            "--image",
            self.last_image_path,
            "--prompt",
            prompt or "animate the scene",
            "--duration",
            "5",
            "--poll",
            "900",
        ]

        yield event.plain_result(
            f"正在将图片动画化：{prompt or '（默认动效）'}\n这可能需要较长时间..."
        )

        success, output = await self._execute_dreamina(command, timeout=900)

        if success:
            gen_ok, fail_reason = self._check_gen_status(output)
            if not gen_ok:
                yield event.plain_result(f"生成失败：{fail_reason}")
                return
            url_match = re.search(r'https?://[^\s<>"]+\.mp4[^\s<>"]*', output)
            if url_match:
                yield event.plain_result(f"视频生成成功：{url_match.group()}")
            else:
                yield event.plain_result(f"生成成功！\n{output[:500]}")
        else:
            yield event.plain_result(f"生成失败：{output}")

    @filter.command("即梦余额")
    async def check_credit(self, event: AstrMessageEvent):
        """查询账户余额"""
        command = ["user_credit"]

        success, output = await self._execute_dreamina(command, timeout=30)

        if success:
            try:
                # 尝试解析 JSON
                json_match = re.search(r"\{[^{}]*\}", output, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    credit = data.get("credit", "未知")
                    yield event.plain_result(
                        f"即梦账户余额：{credit} 积分\n"
                        f"API Key 后六位：{self.api_key_suffix}\n"
                        f"提醒阈值：{self.credit_threshold} 积分"
                    )
                else:
                    yield event.plain_result(output)
            except:
                yield event.plain_result(output)
        else:
            yield event.plain_result(f"查询失败：{output}")

    @filter.command("设置余额提醒")
    async def set_credit_threshold(
        self, event: AstrMessageEvent, threshold: int = None
    ):
        """设置余额提醒阈值"""
        if threshold is None:
            yield event.plain_result(
                f"当前余额提醒阈值：{self.credit_threshold} 积分\n"
                f"使用方法：/设置余额提醒 <阈值>\n"
                f"例如：/设置余额提醒 50"
            )
            return

        if threshold < 0:
            yield event.plain_result("阈值必须大于 0")
            return

        self.credit_threshold = threshold
        yield event.plain_result(f"✅ 余额提醒阈值已设置为：{threshold} 积分")

    @filter.command("即梦任务列表")
    async def list_tasks(self, event: AstrMessageEvent, status: str = ""):
        """查询任务列表"""
        command = ["list_task"]

        if status:
            command.extend(["--gen_status", status])

        success, output = await self._execute_dreamina(command, timeout=60)

        if success:
            yield event.plain_result(output[:2000] if len(output) > 2000 else output)
        else:
            yield event.plain_result(f"查询失败：{output}")

    @filter.command("查询即梦任务")
    async def query_task(self, event: AstrMessageEvent, submit_id: str):
        """查询特定任务结果"""
        if not submit_id:
            yield event.plain_result(
                "请提供任务 ID，例如：/查询即梦任务 3f6eb41f425d23a3"
            )
            return

        command = ["query_result", "--submit_id", submit_id]

        success, output = await self._execute_dreamina(command, timeout=60)

        if success:
            yield event.plain_result(output)
        else:
            yield event.plain_result(f"查询失败：{output}")

    # ── LLM Tool：让 LLM 自己决定何时调用，彻底避免与 LLM 管道冲突 ──

    @filter.llm_tool(name="dreamina_generate_image")
    async def tool_text2image(self, event: AstrMessageEvent, prompt: str):
        """根据用户描述生成图片。当用户想要画图、生成图片、制作插画等时调用此工具。

        Args:
            prompt(string): 图片内容描述，直接使用用户的原始描述
        """
        event.stop_event()
        yield
        command = [
            "text2image",
            "--prompt",
            prompt,
            "--ratio",
            "1:1",
            "--resolution_type",
            "2k",
            "--poll",
            "600",
        ]
        yield event.plain_result(f"正在生成图片：{prompt}\n这可能需要几分钟时间...")
        success, output = await self._execute_dreamina(command, timeout=600)
        if success:
            gen_ok, fail_reason = self._check_gen_status(output)
            if not gen_ok:
                yield event.plain_result(f"生成失败：{fail_reason}")
                return
            url_match = re.search(r'https?://[^\s<>"]+\.(?:jpg|png)[^\s<>"]*', output)
            if url_match:
                image_url = url_match.group()
                try:
                    suffix = ".png" if ".png" in image_url else ".jpg"
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                    tmp.close()
                    await asyncio.to_thread(
                        urllib.request.urlretrieve, image_url, tmp.name
                    )
                    self.last_image_path = tmp.name
                    yield event.image_result(image_url)
                    yield event.plain_result(
                        "图片已保存，可以直接说「把这张图做成视频」"
                    )
                except Exception as e:
                    logger.warning(f"图片下载失败：{e}")
                    yield event.image_result(image_url)
            else:
                yield event.plain_result(f"生成成功！\n{output[:500]}")
        else:
            yield event.plain_result(f"生成失败：{output}")

    @filter.llm_tool(name="dreamina_animate_image")
    async def tool_image2video(self, event: AstrMessageEvent, prompt: str):
        """将最近生成的图片动画化为视频。当用户想把已有图片做成动画、视频、动效时调用。

        Args:
            prompt(string): 动画描述，如"镜头缓慢推进"、"人物慢慢转身"等
        """
        event.stop_event()
        yield
        if not self.last_image_path or not os.path.exists(self.last_image_path):
            yield event.plain_result("没有找到最近生成的图片，请先生成一张图片")
            return
        command = [
            "image2video",
            "--image",
            self.last_image_path,
            "--prompt",
            prompt or "animate the scene",
            "--duration",
            "5",
            "--poll",
            "900",
        ]
        yield event.plain_result(f"正在将图片动画化：{prompt}\n这可能需要较长时间...")
        success, output = await self._execute_dreamina(command, timeout=900)
        if success:
            gen_ok, fail_reason = self._check_gen_status(output)
            if not gen_ok:
                yield event.plain_result(f"生成失败：{fail_reason}")
                return
            url_match = re.search(r'https?://[^\s<>"]+\.mp4[^\s<>"]*', output)
            if url_match:
                yield event.plain_result(f"视频生成成功：{url_match.group()}")
            else:
                yield event.plain_result(f"生成成功！\n{output[:500]}")
        else:
            yield event.plain_result(f"生成失败：{output}")

    @filter.llm_tool(name="dreamina_generate_video")
    async def tool_text2video(self, event: AstrMessageEvent, prompt: str):
        """根据用户描述生成视频。当用户想生成视频、动画、短片时调用（不依赖已有图片）。

        Args:
            prompt(string): 视频内容描述，直接使用用户的原始描述
        """
        event.stop_event()
        yield
        command = [
            "text2video",
            "--prompt",
            prompt,
            "--duration",
            "5",
            "--ratio",
            "16:9",
            "--video_resolution",
            "720p",
            "--poll",
            "900",
        ]
        yield event.plain_result(f"正在生成视频：{prompt}\n这可能需要较长时间...")
        success, output = await self._execute_dreamina(command, timeout=900)
        if success:
            gen_ok, fail_reason = self._check_gen_status(output)
            if not gen_ok:
                yield event.plain_result(f"生成失败：{fail_reason}")
                return
            url_match = re.search(r'https?://[^\s<>"]+\.mp4[^\s<>"]*', output)
            if url_match:
                yield event.plain_result(f"视频生成成功：{url_match.group()}")
            else:
                yield event.plain_result(f"生成成功！\n{output[:500]}")
        else:
            yield event.plain_result(f"生成失败：{output}")
