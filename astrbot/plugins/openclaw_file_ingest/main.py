"""
OpenClaw QQ 文件接收与智库入库插件

流程：
1. 用户在 QQ 聊天窗口直接发送文件
2. 机器人检测到文件，根据文件名+扩展名自动猜测分类
3. 向用户展示猜测结果 + 完整分类列表，请求确认
4. 用户回复选项字母（可附品牌名），机器人将文件保存到本地智库对应目录
5. 无法识别时给出明确引导，避免用户困惑
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp

from astrbot.api import star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core.message.components import File as FileComponent

logger = logging.getLogger("openclaw.plugins.file_ingest")

# ─────────────────────────────────────────────
# 本地智库根目录（与 HarnessConfig 保持一致）
# ─────────────────────────────────────────────
KNOWLEDGE_ROOT = Path(os.getenv(
    "OPENCLAW_KNOWLEDGE_ROOT",
    "/Users/dianchi/Openclaw/docs/company_knowledge"
))
PENDING_ROOT = Path(os.getenv(
    "OPENCLAW_KNOWLEDGE_ROOT",
    "/Users/dianchi/Openclaw/docs/company_knowledge"
)).parent / "pending_uploads"

# ─────────────────────────────────────────────
# 分类定义（字母 → 目录名 + 中文标签）
# ─────────────────────────────────────────────
CATEGORIES: Dict[str, Dict[str, str]] = {
    "A": {"dir": "brand_guidelines",      "label": "品牌规范"},
    "B": {"dir": "past_copywriting",       "label": "历史文案"},
    "C": {"dir": "campaign_reviews",       "label": "活动复盘"},
    "D": {"dir": "client_material",        "label": "客户资料"},
    "E": {"dir": "competitor_cases",       "label": "竞品案例"},
    "F": {"dir": "project_plan",           "label": "项目方案"},
    "G": {"dir": "daily_weekly_report",    "label": "日报/周报"},
    "H": {"dir": "data_report",            "label": "数据报表"},
    "I": {"dir": "top_performing_scripts", "label": "爆款案例"},
    "J": {"dir": "client_feedback",        "label": "客户反馈"},
    "K": {"dir": "other_material",         "label": "其他资料"},
}

# 扩展名 → 推荐分类字母（粗分类提示，仅供参考）
EXT_HINTS: Dict[str, str] = {
    ".pptx": "F", ".ppt": "F",                    # 演示文稿 → 项目方案
    ".docx": "B", ".doc": "B",                     # Word → 历史文案（最常见）
    ".xlsx": "H", ".xls": "H", ".csv": "H",        # 表格 → 数据报表
    ".pdf": "D",                                   # PDF → 客户资料
    ".md": "B", ".txt": "B",                       # 文本 → 历史文案
    ".jpg": "B", ".jpeg": "B", ".png": "B",        # 图片 → 历史文案（设计稿等）
}

# 文件名关键词 → 推荐分类字母
KEYWORD_HINTS: Dict[str, str] = {
    "品牌": "A", "vi": "A", "logo": "A", "规范": "A",
    "文案": "B", "copy": "B", "脚本": "B", "内容": "B",
    "复盘": "C", "总结": "C", "回顾": "C", "活动": "C",
    "客户": "D", "合同": "D", "需求": "D",
    "竞品": "E", "对手": "E", "competitor": "E",
    "方案": "F", "策划": "F", "proposal": "F",
    "日报": "G", "周报": "G", "月报": "G",
    "数据": "H", "报表": "H", "analytics": "H",
    "爆款": "I", "案例": "I",
    "反馈": "J", "意见": "J", "评价": "J",
}

# ─────────────────────────────────────────────
# 用户会话状态（内存，进程级别）
# key = sender_id, value = 待确认文件信息
# ─────────────────────────────────────────────
_pending: Dict[str, Dict[str, Any]] = {}


def _guess_category(filename: str) -> Optional[str]:
    """根据文件名+扩展名猜测分类字母，无把握则返回 None。"""
    name_lower = filename.lower()
    ext = Path(filename).suffix.lower()

    # 关键词优先（更精确）
    for kw, cat in KEYWORD_HINTS.items():
        if kw in name_lower:
            return cat

    # 扩展名兜底
    return EXT_HINTS.get(ext)


def _categories_menu(highlight: Optional[str] = None) -> str:
    lines = []
    for letter, info in CATEGORIES.items():
        mark = " ← 推测" if letter == highlight else ""
        lines.append(f"  {letter}. {info['label']}{mark}")
    return "\n".join(lines)


def _save_file(pending_path: Path, filename: str, category_letter: str, brand: str) -> Path:
    """将 pending 文件移动到本地智库对应目录，返回最终路径。"""
    cat_dir = CATEGORIES[category_letter]["dir"]
    brand_slug = brand.strip() if brand.strip() else "general"
    target_dir = KNOWLEDGE_ROOT / cat_dir / brand_slug
    target_dir.mkdir(parents=True, exist_ok=True)

    # 避免重名
    safe_name = filename
    target_path = target_dir / safe_name
    if target_path.exists():
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        safe_name = f"{stem}_{uuid.uuid4().hex[:6]}{suffix}"
        target_path = target_dir / safe_name

    shutil.move(str(pending_path), target_path)
    return target_path


async def _download_file(url: str, dest: Path) -> None:
    """从 URL 下载文件到本地。"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)


@star.register(
    "openclaw_file_ingest",
    "OpenClaw Team",
    "QQ文件接收与本地智库入库",
    "1.0.0",
)
class OpenClawFileIngestPlugin(star.Star):

    def __init__(self, context):
        super().__init__(context)
        KNOWLEDGE_ROOT.mkdir(parents=True, exist_ok=True)
        PENDING_ROOT.mkdir(parents=True, exist_ok=True)
        logger.info("QQ文件接收插件加载成功，智库目录：%s", KNOWLEDGE_ROOT)

    # ──────────────────────────────────────────
    # 核心：监听所有消息，检测 File 组件
    # ──────────────────────────────────────────
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        messages = event.get_messages()
        sender = event.get_sender_id()

        # ── 情况1：消息中包含文件附件 ────────────────
        file_components = [m for m in messages if isinstance(m, FileComponent)]
        if file_components:
            fc = file_components[0]  # 每次处理第一个文件
            filename = (fc.name or "未命名文件").strip() or "未命名文件"
            file_url = fc.url or fc.file_ or ""

            if not file_url:
                yield event.plain_result(
                    f"⚠️ 收到文件「{filename}」，但无法获取下载链接。\n"
                    "请尝试重新发送，或改用 /kb_upload <本地路径> 方式上传。"
                )
                return

            # 下载文件到 pending 目录
            pending_path = PENDING_ROOT / f"{uuid.uuid4().hex}__{filename}"
            try:
                await _download_file(file_url, pending_path)
            except Exception as e:
                logger.error("文件下载失败 %s: %s", filename, e)
                yield event.plain_result(
                    f"⚠️ 文件「{filename}」下载失败（{e}）。\n"
                    "请检查网络或改用 /kb_upload 上传本地文件。"
                )
                return

            guess = _guess_category(filename)
            guess_label = CATEGORIES[guess]["label"] if guess else None

            # 保存待确认状态
            _pending[sender] = {
                "filename": filename,
                "pending_path": pending_path,
                "guess": guess,
            }

            # 构造提示消息
            if guess_label:
                hint_line = f"\n根据文件名，我猜这是「{guess_label}」（选项 {guess}）。"
            else:
                hint_line = "\n我无法从文件名判断类型，请手动选择。"

            menu = _categories_menu(highlight=guess)
            reply = (
                f"📎 收到文件：{filename}{hint_line}\n\n"
                f"请回复选项字母确认分类：\n{menu}\n\n"
                "💡 如需指定品牌，请在字母后加品牌名，例如：\n"
                "   A 柳州五菱\n"
                "   C（不填品牌则归入 general）\n\n"
                "回复 取消 可放弃本次入库。"
            )
            yield event.plain_result(reply)
            return

        # ── 情况2：用户正在回复分类确认 ───────────────
        if sender in _pending:
            raw = (event.message_str or "").strip()

            if raw in ("取消", "cancel", "Cancel"):
                info = _pending.pop(sender)
                # 清理 pending 文件
                try:
                    Path(info["pending_path"]).unlink(missing_ok=True)
                except Exception:
                    pass
                yield event.plain_result("✅ 已取消，文件未入库。")
                return

            # 解析 "字母 [品牌]"
            parts = raw.split(None, 1)
            letter = parts[0].upper() if parts else ""
            brand = parts[1].strip() if len(parts) > 1 else ""

            if letter not in CATEGORIES:
                menu = _categories_menu(_pending[sender].get("guess"))
                yield event.plain_result(
                    f"❓ 「{raw}」不是有效的选项。\n\n"
                    f"请从以下选项中选择：\n{menu}\n\n"
                    "或回复 取消 放弃入库。"
                )
                return

            # 执行入库
            info = _pending.pop(sender)
            pending_path = Path(info["pending_path"])
            filename = info["filename"]

            if not pending_path.exists():
                yield event.plain_result("⚠️ 文件已丢失，请重新发送文件。")
                return

            try:
                final_path = _save_file(pending_path, filename, letter, brand)
            except Exception as e:
                logger.error("文件入库失败 %s: %s", filename, e)
                yield event.plain_result(f"❌ 入库失败：{e}")
                return

            cat_label = CATEGORIES[letter]["label"]
            brand_display = brand if brand else "general"
            yield event.plain_result(
                f"✅ 入库成功！\n\n"
                f"📄 文件：{filename}\n"
                f"📂 分类：{cat_label}\n"
                f"🏷️ 品牌：{brand_display}\n"
                f"📍 路径：{final_path}"
            )
