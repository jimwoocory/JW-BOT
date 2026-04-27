"""
MiniMax Token 监控插件 - 定期检查 MiniMax API 余额并提醒
"""
import aiohttp
import json
import os
from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Star, register


@register(
    "minimax_token_plugin",
    "minimax_token_plugin",
    "MiniMax Token 余额监控插件，支持定时检查和余额提醒",
    "0.0.1"
)
class MiniMaxTokenPlugin(Star):
    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context
        self.api_key = ""
        self.credit_threshold = 1000
        self.weekly_limit = 5000  # 周上限额度
        self.api_key_suffix = "lVJnPr"
        self.check_interval_hours = 6
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.api_base_url = "https://minimax.a7m.com.cn"
        self.balance_endpoint = "/v1/api/balance"
        
    async def initialize(self) -> None:
        """插件初始化"""
        try:
            # 从配置文件读取配置
            await self._load_config()
            
            if not self.api_key or self.api_key == "your_minimax_api_key_here":
                logger.warning("⚠️ MiniMax API Key 未配置，请编辑 config.json 文件")
            else:
                logger.info(f"✅ MiniMax API Key 已加载（后六位：{self.api_key_suffix}）")
                # 注册定时检查任务
                await self._register_cron_check()
        except Exception as e:
            logger.error(f"❌ 初始化失败：{e}")
    
    async def _load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.api_key = config.get("api_key", "")
                    self.api_key_suffix = config.get("api_key_suffix", "lVJnPr")
                    self.credit_threshold = config.get("credit_threshold", 1000)
                    self.weekly_limit = config.get("weekly_limit", 5000)
                    self.check_interval_hours = config.get("check_interval_hours", 6)
                    self.api_base_url = config.get("api_base_url", "https://minimax.a7m.com.cn")
                    self.balance_endpoint = config.get("balance_endpoint", "/v1/api/balance")
        except Exception as e:
            logger.error(f"❌ 加载配置文件失败：{e}")
    
    async def _register_cron_check(self):
        """注册定时检查余额任务"""
        try:
            # 根据配置设置检查频率
            cron_expression = f"0 */{self.check_interval_hours} * * *"
            await self.context.cron_manager.add_basic_job(
                name="minimax_token_check",
                cron_expression=cron_expression,
                handler=self._scheduled_token_check,
                description="MiniMax Token 余额定时检查",
                timezone="Asia/Shanghai",
                persistent=True,
            )
            logger.info(f"✅ MiniMax Token 定时检查任务已注册（每 {self.check_interval_hours} 小时）")
        except Exception as e:
            logger.error(f"❌ 注册定时检查任务失败：{e}")
    
    async def _scheduled_token_check(self):
        """定时检查余额（由 cron 触发）"""
        try:
            if not self.api_key:
                logger.warning("⚠️ MiniMax API Key 未配置，跳过检查")
                return
            
            credit = await self._query_credit()
            
            if credit is not None:
                usage = self.weekly_limit - credit  # 已使用量
                usage_percent = (usage / self.weekly_limit) * 100
                
                if credit < self.credit_threshold:
                    logger.warning(
                        f"⚠️ MiniMax Token 余额不足！当前余额：{credit} / {self.weekly_limit}，"
                        f"已使用：{usage} ({usage_percent:.1f}%)，阈值：{self.credit_threshold}，"
                        f"API Key 后六位：{self.api_key_suffix}"
                    )
                else:
                    logger.info(
                        f"✅ MiniMax Token 余额正常：剩余 {credit} / {self.weekly_limit}，"
                        f"已使用：{usage} ({usage_percent:.1f}%)，API Key 后六位：{self.api_key_suffix}"
                    )
        except Exception as e:
            logger.error(f"❌ 定时检查余额失败：{e}")
    
    async def _query_credit(self) -> int | None:
        """查询 MiniMax Token 余额
        
        Returns:
            余额数量，失败返回 None
        """
        if not self.api_key:
            return None
        
        # 使用中转服务商的 API 地址
        url = f"{self.api_base_url}{self.balance_endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 中转商通常返回格式：{"balance": 12345} 或 {"data": {"balance": 12345}}
                        if "balance" in data:
                            return data["balance"]
                        elif "data" in data and "balance" in data["data"]:
                            return data["data"]["balance"]
                        elif "remaining_tokens" in data:
                            return data["remaining_tokens"]
                        elif "data" in data and "remaining_tokens" in data["data"]:
                            return data["data"]["remaining_tokens"]
                        elif "total_tokens" in data:
                            return data["total_tokens"]
                        elif "data" in data and "total_tokens" in data["data"]:
                            return data["data"]["total_tokens"]
                    else:
                        error_text = await response.text()
                        logger.error(f"查询余额失败：HTTP {response.status} - {error_text}")
        except aiohttp.ClientError as e:
            logger.error(f"网络错误：{e}")
        except Exception as e:
            logger.error(f"查询异常：{e}")
        
        return None
    
    @filter.command("minimax 余额")
    async def check_credit(self, event: AstrMessageEvent):
        """查询 MiniMax 账户余额"""
        if not self.api_key:
            yield event.plain_result("❌ 未配置 MiniMax API Key")
            return
        
        yield event.plain_result("正在查询 MiniMax Token 余额...")
        
        credit = await self._query_credit()
        
        if credit is not None:
            usage = self.weekly_limit - credit  # 已使用量
            usage_percent = (usage / self.weekly_limit) * 100
            
            yield event.plain_result(
                f"📊 MiniMax Token 用量查询\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"周上限额度：{self.weekly_limit:,}\n"
                f"剩余余额：{credit:,}\n"
                f"已使用：{usage:,} ({usage_percent:.1f}%)\n"
                f"提醒阈值：{self.credit_threshold:,}\n"
                f"API Key 后六位：{self.api_key_suffix}"
            )
        else:
            yield event.plain_result(
                "查询失败，请检查：\n"
                "1. API Key 是否正确\n"
                "2. 网络连接是否正常\n"
                "3. 是否购买了 Token Plan"
            )
    
    @filter.command("设置 minimax 提醒")
    async def set_credit_threshold(self, event: AstrMessageEvent, threshold: int = None):
        """设置 MiniMax 余额提醒阈值"""
        if threshold is None:
            yield event.plain_result(
                f"当前 MiniMax 余额提醒阈值：{self.credit_threshold:,}\n"
                f"周上限额度：{self.weekly_limit:,}\n"
                f"使用方法：/设置 minimax 提醒 <阈值>\n"
                f"例如：/设置 minimax 提醒 500"
            )
            return
        
        if threshold < 0:
            yield event.plain_result("阈值必须大于 0")
            return
        
        self.credit_threshold = threshold
        yield event.plain_result(f"✅ MiniMax 余额提醒阈值已设置为：{threshold:,}")
    
    @filter.command("设置 minimax 周额度")
    async def set_weekly_limit(self, event: AstrMessageEvent, limit: int = None):
        """设置 MiniMax 周上限额度"""
        if limit is None:
            yield event.plain_result(
                f"当前 MiniMax 周上限额度：{self.weekly_limit:,}\n"
                f"使用方法：/设置 minimax 周额度 <额度>\n"
                f"例如：/设置 minimax 周额度 5000"
            )
            return
        
        if limit < 0:
            yield event.plain_result("周额度必须大于 0")
            return
        
        self.weekly_limit = limit
        yield event.plain_result(f"✅ MiniMax 周上限额度已设置为：{limit:,}")
    
    @filter.command("minimax 测试")
    async def test_connection(self, event: AstrMessageEvent):
        """测试 MiniMax API 连接"""
        if not self.api_key:
            yield event.plain_result("❌ 未配置 MiniMax API Key")
            return
        
        yield event.plain_result("正在测试 MiniMax API 连接...")
        
        credit = await self._query_credit()
        
        if credit is not None:
            usage = self.weekly_limit - credit
            usage_percent = (usage / self.weekly_limit) * 100
            
            yield event.plain_result(
                f"✅ 连接成功！\n"
                f"API Key 后六位：{self.api_key_suffix}\n"
                f"周上限额度：{self.weekly_limit:,}\n"
                f"剩余余额：{credit:,}\n"
                f"已使用：{usage:,} ({usage_percent:.1f}%)"
            )
        else:
            yield event.plain_result("❌ 连接失败，请检查 API Key 和网络")
