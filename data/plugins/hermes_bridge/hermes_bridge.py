"""
AstrBot ↔ Hermes Agent 双向桥接插件（方案 C 协作架构）

职责：
1. 用户消息转发给 Hermes（仅 /hermes on 模式）
2. Router 创建的 Harness workflow 任务派发给 Hermes 执行
3. 接收 Hermes 结果 → 完成 Harness 任务 → 推送回原平台用户
4. 长期任务记忆注入 → 每次 LLM 调用前注入近期任务摘要到 system_prompt

配置（hermes_bridge section）：
  webhook_url:      Hermes 消息 Webhook（默认 http://localhost:8644/webhooks/astrbot_qq）
  task_webhook_url: Hermes 任务 Webhook（默认 http://localhost:8644/webhooks/astrbot_task）
  secret:           HMAC 签名密钥
  response_port:    本地响应监听端口（默认 8645）
  allowed_platforms: 允许转发的平台列表
  memory_inject_enabled: 是否注入长期任务记忆（默认 True）
  memory_inject_limit:   注入最近几条记忆（默认 5）
"""

import asyncio
import hashlib
import hmac
import json

# ── SessionRouter ─────────────────────────────────────────────────────────────
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Plain
from astrbot.api.provider import LLMResponse, ProviderRequest
from astrbot.api.star import Context, Star, register
from astrbot.core.harness import create_workflow_request
from astrbot.core.harness.contracts import HARNESS_TERMINAL_STATUSES
from astrbot.core.hermes_callback_dispatcher import (
    HermesCallbackDispatcher,
    PermanentSendError,
    RetriableSendError,
    classify_http_status,
    verify_hmac_signature,
)
from astrbot.core.hermes_dlq_logger import HermesDLQLogger


class PlatformType(str, Enum):
    QQ = "qq"
    FEISHU = "feishu"
    WEBUI = "webui"
    WECHAT = "wechat"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, value: str) -> "PlatformType":
        try:
            return cls(value.lower())
        except ValueError:
            raise ValueError(f"Unknown platform: {value}")

    @classmethod
    def from_astrbot_platform_id(cls, platform_id: str) -> "PlatformType":
        _map = {
            "qq_official": cls.QQ,
            "lark": cls.FEISHU,
            "webchat": cls.WEBUI,
        }
        result = _map.get(platform_id.lower())
        if result is not None:
            return result
        try:
            return cls.from_string(platform_id)
        except ValueError:
            return cls.UNKNOWN


@dataclass
class PlatformUser:
    platform: PlatformType
    user_id: str


class SessionRouter:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_mappings (
                    platform TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    session_key TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now')),
                    PRIMARY KEY (platform, user_id)
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def get_or_create_session(self, user: PlatformUser) -> str:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT session_key FROM session_mappings WHERE platform=? AND user_id=?",
                (user.platform.value, user.user_id),
            ).fetchone()
            if row:
                return row[0]
            key = f"{user.platform.value}_{user.user_id}_{uuid.uuid4().hex[:8]}"
            conn.execute(
                "INSERT INTO session_mappings (platform, user_id, session_key) VALUES (?,?,?)",
                (user.platform.value, user.user_id, key),
            )
            return key

    def get_platform_user_by_session(self, session_key: str) -> PlatformUser | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT platform, user_id FROM session_mappings WHERE session_key=?",
                (session_key,),
            ).fetchone()
            if row:
                return PlatformUser(platform=PlatformType(row[0]), user_id=row[1])
            return None


# ── Plugin ────────────────────────────────────────────────────────────────────


@register(
    "hermes_bridge",
    "hermes_bridge",
    "AstrBot ↔ Hermes 双向桥接（方案 C 协作架构）",
    version="2.0.0",
)
class HermesBridgePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        cfg = context.get_config()
        hcfg = cfg.get("hermes_bridge", {})

        self.hermes_webhook_url: str = hcfg.get(
            "webhook_url", "http://localhost:8644/webhooks/astrbot_qq"
        )
        self.hermes_task_webhook_url: str = hcfg.get(
            "task_webhook_url", "http://localhost:8644/webhooks/astrbot_task"
        )
        self.hermes_secret: str = hcfg.get("secret", "astrbot-secret-key")
        self.response_port: int = hcfg.get("response_port", 8645)
        self.allowed_platforms: list = hcfg.get(
            "allowed_platforms",
            ["巅池-推广01", "巅池-推广 01", "巅池1号"],
        )
        self.excluded_platforms: list = hcfg.get("excluded_platforms", ["巅池-技术"])
        self.memory_inject_enabled: bool = hcfg.get("memory_inject_enabled", True)
        self.memory_inject_limit: int = int(hcfg.get("memory_inject_limit", 5))
        self.direct_chat_enabled: bool = hcfg.get("direct_chat_enabled", False)
        self.topic_workflow_enabled: bool = hcfg.get("topic_workflow_enabled", True)
        self.topic_admin_only: bool = hcfg.get("topic_admin_only", True)
        self.topic_intro_on_new: bool = hcfg.get("topic_intro_on_new", True)
        self.topic_discussion_limit: int = int(hcfg.get("topic_discussion_limit", 30))
        self.topic_distill_enabled: bool = hcfg.get("topic_distill_enabled", True)

        # 持久化路径：默认仓库 data/ 目录，允许 hcfg.data_dir 覆盖（测试 / 私有部署）
        data_dir_override = hcfg.get("data_dir")
        if data_dir_override:
            data_dir = Path(data_dir_override)
            data_dir.mkdir(parents=True, exist_ok=True)
        else:
            data_dir = Path(__file__).resolve().parents[3] / "data"
        self.session_router = SessionRouter(str(data_dir / "hermes_sessions.db"))

        # session_key → unified_msg_origin 内存缓存（重启后首条消息重建）
        self._umo_cache: dict[str, str] = {}

        # 回群链路 DLQ + 重试调度器（G2 / Phase 0.3）
        self._dlq_logger = HermesDLQLogger(data_dir / "hermes_dlq.jsonl")
        self._callback_dispatcher = HermesCallbackDispatcher(
            sender=self._send_to_platform_strict,
            dlq_logger=self._dlq_logger,
        )

        # /hermes on 已启用的用户集合
        self.hermes_enabled_users: set[str] = set()
        self._topic_discussion_cache: dict[str, deque[dict]] = defaultdict(
            lambda: deque(maxlen=self.topic_discussion_limit)
        )
        self._topic_rollcall: dict[str, dict] = {}

        self._webhook_app = None
        logger.info(
            "[HermesBridge] 初始化完成，消息 Webhook: %s", self.hermes_webhook_url
        )
        logger.info("[HermesBridge] 任务 Webhook: %s", self.hermes_task_webhook_url)

    async def initialize(self):
        await self._start_response_server()
        logger.info("[HermesBridge] 响应服务器启动，监听 port %s", self.response_port)

    # ── 长期任务记忆注入（LLM 调用前钩子） ────────────────────────────────────

    @filter.on_llm_request()
    async def inject_harness_memory(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        """
        长期记忆注入 — 参考 memory-lancedb-pro 的 hybrid recall 思路（简化版）。

        两层记忆架构：
          短期 = AstrBot 对话窗口（已有，protect last-N 理念来自 lossless-claw）
          长期 = Harness task memory（此处注入）

        排序策略（简化 hybrid score）：
          score = recency_weight * 0.5 + domain_relevance * 0.5
          recency_weight  : 越新越高（指数衰减，半衰期 7 天）
          domain_relevance: 当前消息关键词命中记忆 domain/title 越多得分越高
        """
        if not self.memory_inject_enabled:
            return

        try:
            engine = self.context.harness_engine
            if engine is None or engine.memory_promoter is None:
                return

            memory_store = engine.memory_promoter.store
            # 多取一些，由本地 scoring 再筛出 top-N
            candidates = await memory_store.list_for_session(
                event.unified_msg_origin,
                limit=self.memory_inject_limit * 3,
            )
            if not candidates:
                return

            scored = self._score_memories(event.message_str, candidates)
            top = scored[: self.memory_inject_limit]

            lines = [
                "# 工作记忆（历史任务摘要，供回答参考，无需向用户重复）",
            ]
            for mem, _score in top:
                date_str = mem.created_at[:10]
                lines.append(f"- [{date_str}][{mem.domain}] {mem.title}：{mem.summary}")

            memory_block = "\n".join(lines)
            req.system_prompt = (req.system_prompt or "") + f"\n\n{memory_block}\n"

            logger.debug(
                "[HermesBridge] 长期记忆注入：session=%s, 注入=%d条（候选=%d条）",
                event.unified_msg_origin,
                len(top),
                len(candidates),
            )

        except Exception as exc:
            logger.debug("[HermesBridge] 长期记忆注入失败（不影响正常流程）：%s", exc)

    def _score_memories(
        self,
        message: str,
        memories: list,
    ) -> list[tuple]:
        """
        对候选记忆打分，返回 [(memory, score), ...] 降序排列。

        score = 0.5 * recency + 0.5 * domain_relevance

        recency       : 指数衰减，半衰期 7 天（参考 Weibull decay 思路）
        domain_relevance: CJK 感知的 n-gram 子串匹配
                          提取消息中所有 2~4 字子串，检查在记忆文本中出现的比例
                          （避免中文无空格分词问题，参考 lossless-claw 的 CJK 处理）
        """
        import math
        from datetime import datetime, timezone

        msg = message.lower()
        # 提取 2~4 字 n-gram（兼容中英文混合）
        ngrams: set[str] = set()
        for n in (2, 3, 4):
            for i in range(len(msg) - n + 1):
                chunk = msg[i : i + n].strip()
                if chunk:
                    ngrams.add(chunk)

        now = datetime.now(timezone.utc)
        results = []

        for mem in memories:
            # ── Recency score（指数衰减，半衰期 7 天）──────────────────────────
            try:
                created = datetime.fromisoformat(mem.created_at)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                days_old = max(0.0, (now - created).total_seconds() / 86400)
                recency = math.exp(-0.693 * days_old / 7.0)
            except Exception:
                recency = 0.5

            # ── Domain relevance score（n-gram 子串匹配）────────────────────
            target = f"{mem.domain} {mem.title} {mem.summary}".lower()
            if ngrams:
                hits = sum(1 for ng in ngrams if ng in target)
                domain_score = min(1.0, hits / max(1, len(ngrams)) * 5)
            else:
                domain_score = 0.0

            score = 0.5 * recency + 0.5 * domain_score
            results.append((mem, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    # ── AstrBot LLM 回答后：完成 pending 任务 → 触发记忆写入 ─────────────────

    @filter.on_llm_response()
    async def complete_pending_harness_task(
        self,
        event: AstrMessageEvent,
        resp: LLMResponse,
    ) -> None:
        """
        AstrBot LLM 回答完毕后，将该 session 中 pending 状态的 Harness 任务
        标记为 completed，触发 HarnessMemoryPromoter 写入长期记忆。

        状态区分：
          pending    → AstrBot LLM 刚处理完，此处 complete → 写记忆 ✅
          in_progress → 已派发给 Hermes，跳过（等 Hermes 回传再 complete）⏭️
        """
        try:
            engine = self.context.harness_engine
            if engine is None:
                return

            tasks = await engine.store.list_tasks_for_session(
                event.unified_msg_origin,
                limit=1,
                statuses=("pending",),
            )
            if not tasks:
                return

            task = tasks[0]

            # 仅处理 RouterStage 创建、由 AstrBot LLM 直接处理的任务
            # source="router_intent"      → _handle_task_intent 创建，LLM 先答，此处 complete ✅
            # source="satisfaction_escalation" → 已被 mark_in_progress，status≠pending，不会走到这里
            # 其他 source（如手动 /task intake）→ 跳过
            source = task.payload.get("source", "")
            if source != "router_intent":
                return

            response_text = (resp.completion_text or "").strip()
            await engine.complete_task(
                task.task_id,
                result={
                    "summary": response_text[:200],
                    "response_preview": response_text[:500],
                    "source": "astrbot_llm",
                },
            )
            logger.debug(
                "[HermesBridge] AstrBot LLM 回答已完成 Harness 任务（#%s）→ 记忆已写入",
                task.task_id[:8],
            )

        except Exception as exc:
            logger.debug("[HermesBridge] 任务记忆写入失败（不影响正常流程）：%s", exc)

    # ── 消息入站处理 ──────────────────────────────────────────────────────────

    async def on_message(self, event: AstrMessageEvent) -> None:
        try:
            platform_id = str(event.get_platform_id() or "")
            if platform_id in self.excluded_platforms:
                return
            if self.allowed_platforms and platform_id not in self.allowed_platforms:
                return

            message_text = "".join(
                str(c.text) for c in event.get_messages() if isinstance(c, Plain)
            )
            if not message_text.strip():
                return

            user_id = str(event.get_sender_id())

            if user_id and user_id == str(event.get_self_id() or ""):
                return

            # 开关命令
            normalized = message_text.strip().lower()
            if self.topic_workflow_enabled and await self._handle_topic_command(
                event,
                user_id,
                message_text.strip(),
            ):
                event.stop_event()
                return

            if normalized in ("/hermes on", "/hermes off", "/hermes status"):
                await self._handle_toggle(event, user_id, normalized)
                event.stop_event()
                return

            if self.topic_workflow_enabled and await self._handle_rollcall_reply(
                event,
                user_id,
                message_text.strip(),
            ):
                event.stop_event()
                return

            if self.topic_workflow_enabled:
                await self._record_topic_discussion(event, user_id, message_text)

            if not self.direct_chat_enabled:
                return

            # 只有开启 Hermes 模式的用户才转发消息
            if user_id not in self.hermes_enabled_users:
                return

            try:
                platform_type = PlatformType.from_astrbot_platform_id(platform_id)
            except ValueError:
                platform_type = PlatformType.QQ

            session_key = self._get_or_create_session(user_id, platform_type)
            umo = event.unified_msg_origin
            self._umo_cache[session_key] = umo

            await self._send_to_hermes(
                {
                    "user_id": user_id,
                    "session_key": session_key,
                    "unified_msg_origin": umo,
                    "message": message_text,
                    "message_type": "group" if event.is_group() else "private",
                    "platform": platform_type.value,
                    "message_id": str(getattr(event, "message_id", "")),
                    "sender_nickname": event.get_sender_name() or user_id,
                }
            )

        except Exception as exc:
            logger.error("[HermesBridge] on_message 失败：%s", exc)

    # ── 任务派发（由 RouterStage 调用）──────────────────────────────────────

    async def dispatch_task_to_hermes(
        self,
        task_id: str,
        workflow_kind: str,
        brief: str,
        umo: str,
        cognitive_context: dict,
    ) -> bool:
        """将 Harness workflow 任务派发给 Hermes 执行。返回是否成功。"""
        payload = {
            "task_id": task_id,
            "workflow_kind": workflow_kind,
            "brief": brief,
            "session_id": umo,
            "unified_msg_origin": umo,
            "cognitive_context": cognitive_context,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.hermes_task_webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Event": "harness_task",
                        "X-Task-ID": task_id,
                    },
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status in (200, 201, 202):
                        logger.info(
                            "[HermesBridge] 任务 %s 已派发给 Hermes（%s）",
                            task_id,
                            self.hermes_task_webhook_url,
                        )
                        return True
                    logger.warning(
                        "[HermesBridge] Hermes 任务派发失败 HTTP %s: %s",
                        resp.status,
                        await resp.text(),
                    )
                    return False
        except Exception as exc:
            logger.warning("[HermesBridge] Hermes 任务派发异常：%s", exc)
            return False

    # ── Hermes 响应接收 ───────────────────────────────────────────────────────

    async def _start_response_server(self):
        try:
            from aiohttp import web

            app = web.Application()
            app.router.add_post("/hermes_response", self._handle_hermes_response)
            app.router.add_post("/task_result", self._handle_hermes_response)
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", self.response_port).start()
            self._webhook_app = app
        except Exception as exc:
            logger.error("[HermesBridge] 响应服务器启动失败：%s", exc)

    async def _handle_hermes_response(self, request):
        from aiohttp import web

        try:
            body = await request.read()

            # HMAC 入站校验：若 header 带签名，必须校验通过；不带签名按现行行为放行（grace）
            sig_header = request.headers.get("X-Hub-Signature-256", "")
            if sig_header and not verify_hmac_signature(
                self.hermes_secret, body, sig_header
            ):
                logger.warning(
                    "[HermesBridge] X-Hub-Signature-256 校验失败，拒绝回调"
                )
                return web.json_response({"status": "unauthorized"}, status=401)

            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                logger.warning("[HermesBridge] 回调 body 解析失败：%s", exc)
                return web.json_response({"status": "bad_request"}, status=400)

            response_text = data.get("response", "") or data.get("message", "")
            task_id: str | None = data.get("task_id")
            session_key: str = data.get("session_key", "")

            if not response_text:
                logger.warning("[HermesBridge] 收到空响应：%s", data)
                return web.json_response({"status": "ok"})

            # 解析回传地址
            umo: str | None = data.get("unified_msg_origin") or self._umo_cache.get(
                session_key
            )
            if not umo and session_key:
                pu = self.session_router.get_platform_user_by_session(session_key)
                if pu:
                    logger.warning(
                        "[HermesBridge] umo 缓存未命中 session_key=%s，响应可能丢失",
                        session_key,
                    )

            # 完成 Harness 任务
            if task_id:
                await self._complete_harness_task(task_id, response_text)

            # 推送给用户（带重试 + DLQ）
            if not umo:
                logger.error("[HermesBridge] 无法找到回传地址，写入 DLQ")
                await self._dlq_logger.log(
                    {
                        "ts": time.time(),
                        "task_id": task_id,
                        "target_umo": None,
                        "payload": {
                            "message": response_text,
                            "session_key": session_key,
                        },
                        "last_error": "umo_not_found",
                        "attempt_count": 0,
                    }
                )
                return web.json_response(
                    {"status": "queued_to_dlq", "reason": "umo_not_found"},
                    status=202,
                )

            outcome = await self._callback_dispatcher.send_with_retry(
                target_umo=umo,
                message=response_text,
                task_id=task_id,
                extra_payload={"session_key": session_key},
            )
            if outcome.success:
                logger.info(
                    "[HermesBridge] 已将 Hermes 结果推送至 %s (attempts=%d)",
                    umo,
                    outcome.attempts,
                )
                return web.json_response(
                    {"status": "ok", "umo": umo, "attempts": outcome.attempts}
                )

            logger.error(
                "[HermesBridge] 回群失败 umo=%s attempts=%d err=%s dlq=%s",
                umo,
                outcome.attempts,
                outcome.last_error,
                outcome.dlq_written,
            )
            return web.json_response(
                {
                    "status": "queued_to_dlq",
                    "umo": umo,
                    "attempts": outcome.attempts,
                    "last_error": outcome.last_error,
                    "dlq_written": outcome.dlq_written,
                },
                status=202,
            )

        except Exception as exc:
            logger.error("[HermesBridge] 处理响应失败：%s", exc)
            return web.json_response(
                {"status": "error", "message": str(exc)}, status=500
            )

    async def _complete_harness_task(self, task_id: str, response_text: str) -> None:
        engine = getattr(self.context, "harness_engine", None)
        if engine is None:
            return
        try:
            await engine.complete_task(
                task_id,
                result={
                    "summary": response_text[:200],
                    "response_preview": response_text[:500],
                    "source": "hermes",
                },
            )
            logger.info(
                "[HermesBridge] Harness 任务 %s 已通过 Hermes 结果完成", task_id
            )
        except Exception as exc:
            logger.warning("[HermesBridge] 完成 Harness 任务 %s 失败：%s", task_id, exc)

    async def _send_to_platform_strict(self, umo: str, message: str) -> None:
        """通过 AstrBot platform adapter 发送，按错误类型抛 Retriable/Permanent。

        被 HermesCallbackDispatcher 调用。任何不属于"网络层可重试"的异常
        都抛 PermanentSendError，由 dispatcher 决定是否落 DLQ。
        """
        chain = MessageChain([Plain(message)])
        try:
            success = await self.context.send_message(umo, chain)
        except asyncio.TimeoutError as exc:
            raise RetriableSendError(f"timeout: {exc}") from exc
        except aiohttp.ServerDisconnectedError as exc:
            raise RetriableSendError(f"server_disconnected: {exc}") from exc
        except aiohttp.ClientConnectionError as exc:
            raise RetriableSendError(f"connection: {exc}") from exc
        except aiohttp.ClientResponseError as exc:
            cls = classify_http_status(exc.status)
            if cls is RetriableSendError:
                raise RetriableSendError(f"http {exc.status}: {exc}") from exc
            raise PermanentSendError(f"http {exc.status}: {exc}") from exc
        except OSError as exc:
            raise RetriableSendError(f"os: {exc}") from exc
        if not success:
            raise PermanentSendError(
                f"context.send_message returned False for umo={umo}"
            )

    # ── 辅助方法 ──────────────────────────────────────────────────────────────

    async def _send_to_hermes(self, data: dict) -> None:
        try:
            body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            sig = hmac.new(
                self.hermes_secret.encode("utf-8"), body, hashlib.sha256
            ).hexdigest()
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.hermes_webhook_url,
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Hub-Signature-256": f"sha256={sig}",
                        "X-Webhook-Event": "qq_message",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        logger.error(
                            "[HermesBridge] Hermes 消息推送失败 HTTP %s", resp.status
                        )
        except Exception as exc:
            logger.error("[HermesBridge] _send_to_hermes 失败：%s", exc)

    async def _handle_toggle(
        self, event: AstrMessageEvent, user_id: str, cmd: str
    ) -> None:
        if cmd == "/hermes on" and not self.direct_chat_enabled:
            text = (
                "Hermes 直接接管模式当前已关闭。灰度测试请使用 /topic deep "
                "将当前话题交给 Hermes 后台深挖。"
            )
            await event.send(MessageChain([Plain(text)]))
            return

        if cmd == "/hermes on":
            self.hermes_enabled_users.add(user_id)
            text = "Hermes 模式已开启，消息将转发给 Hermes 处理。"
        elif cmd == "/hermes off":
            self.hermes_enabled_users.discard(user_id)
            text = "Hermes 模式已关闭，消息由 AstrBot 默认处理。"
        else:
            text = (
                "当前状态：Hermes 模式已开启。"
                if user_id in self.hermes_enabled_users
                else "当前状态：Hermes 模式已关闭。"
            )
        await event.send(MessageChain([Plain(text)]))

    # ── 灰度话题协作工作流 ────────────────────────────────────────────────────

    async def _handle_topic_command(
        self,
        event: AstrMessageEvent,
        user_id: str,
        text: str,
    ) -> bool:
        normalized = text.strip()
        lower = normalized.lower()
        if not (
            lower.startswith("/topic")
            or lower.startswith("/话题")
            or lower.startswith("/deep")
            or lower.startswith("/深挖")
        ):
            return False

        if self.topic_admin_only and not event.is_admin():
            await event.send(MessageChain([Plain("只有管理员可以操作灰度话题。")]))
            return True

        parts = normalized.split(maxsplit=2)
        root = parts[0].lower()
        action = ""
        body = ""
        if root in ("/deep", "/深挖"):
            action = "deep"
            body = normalized[len(parts[0]) :].strip()
        elif len(parts) >= 2:
            action = parts[1].lower()
            body = parts[2].strip() if len(parts) >= 3 else ""

        if action in ("new", "start", "发布", "新建"):
            await self._topic_new(event, body)
            return True
        if action in ("deep", "research", "深挖", "升级"):
            await self._topic_deep(event, body)
            return True
        if action in ("status", "状态"):
            await self._topic_status(event)
            return True
        if action in ("intro", "guide", "说明", "须知"):
            await self._topic_intro(event)
            return True
        if action in ("rollcall", "点名"):
            await self._topic_rollcall_command(event, body)
            return True
        if action in ("distill", "digest", "蒸馏", "提炼"):
            await self._topic_distill(event)
            return True
        if action in ("close", "done", "关闭", "完成"):
            await self._topic_close(event, user_id, body)
            return True

        await event.send(
            MessageChain(
                [
                    Plain(
                        "灰度话题指令：\n"
                        "- /topic new <话题>\n"
                        "- /topic deep [深挖原因]\n"
                        "- /topic status\n"
                        "- /topic intro\n"
                        "- /topic rollcall start\n"
                        "- /topic distill\n"
                        "- /topic close [结论]"
                    )
                ]
            )
        )
        return True

    async def _topic_new(self, event: AstrMessageEvent, brief: str) -> None:
        if not brief.strip():
            await event.send(
                MessageChain([Plain("请输入话题内容。用法：/topic new <话题>")])
            )
            return

        engine = self.context.harness_engine
        if engine is None:
            await event.send(MessageChain([Plain("Harness 引擎未初始化。")]))
            return

        conversation_id = await self._get_or_create_current_conversation_id(event)
        task = await engine.create_task(
            create_workflow_request(
                workflow_kind="project_followup",
                brief=brief.strip(),
                conversation_id=conversation_id,
                platform_id=event.get_platform_id(),
                session_id=event.unified_msg_origin,
                source="grey_topic",
                message_text=event.message_str,
            )
        )
        await engine.append_trace(
            task.task_id,
            "topic_opened",
            {
                "topic_id": task.task_id,
                "opened_by": event.get_sender_id(),
                "platform_id": event.get_platform_id(),
                "session_id": event.unified_msg_origin,
                "brief": brief.strip(),
            },
        )
        self._topic_discussion_cache[task.task_id].clear()
        self._topic_rollcall.pop(task.task_id, None)

        await event.send(
            MessageChain(
                [
                    Plain(
                        "已发布灰度话题：\n"
                        f"- topic_id: {task.task_id[:8]}\n"
                        f"- task_id: {task.task_id}\n"
                        "- status: discussing\n"
                        "群内后续讨论会挂到这个话题；需要后台深挖时发送 /topic deep。"
                    )
                ]
            )
        )
        if self.topic_intro_on_new:
            await event.send(MessageChain([Plain(self._grey_topic_intro_message())]))

    async def _topic_deep(self, event: AstrMessageEvent, reason: str) -> None:
        engine = self.context.harness_engine
        if engine is None:
            await event.send(MessageChain([Plain("Harness 引擎未初始化。")]))
            return

        task = await self._get_active_topic_task(event)
        if task is None:
            await event.send(MessageChain([Plain("当前群没有进行中的灰度话题。")]))
            return

        discussion = await self._topic_discussion_snapshot(task.task_id)
        deep_reason = reason.strip() or event.message_str.strip()
        distillation = self._distill_grey_topic(
            task,
            discussion,
            trigger_reason=deep_reason,
        )
        await engine.append_trace(
            task.task_id,
            "topic_deep_research_requested",
            {
                "requested_by": event.get_sender_id(),
                "reason": deep_reason,
                "discussion_count": len(discussion),
                "discussion": discussion,
                "distillation": distillation,
            },
        )
        await engine.mark_in_progress(task.task_id, note="topic_deep_research")

        cognitive_context = dict(task.payload.get("cognitive_context", {}) or {})
        cognitive_context["grey_topic"] = {
            "topic_id": task.task_id,
            "title": task.title,
            "status": "needs_deep_research",
            "trigger_reason": deep_reason,
            "discussion": discussion,
            "distillation": distillation,
        }
        cognitive_context["grey_topic_distillation"] = distillation
        ok = await self.dispatch_task_to_hermes(
            task.task_id,
            str(task.payload.get("workflow_kind") or "project_followup"),
            str(task.payload.get("brief") or task.title),
            event.unified_msg_origin,
            cognitive_context,
        )
        status = "Hermes 已开始后台深挖" if ok else "Hermes 派发失败，请稍后重试"
        await event.send(
            MessageChain(
                [
                    Plain(
                        f"{status}：\n"
                        f"- topic_id: {task.task_id[:8]}\n"
                        f"- task_id: {task.task_id}\n"
                        f"- collected_messages: {len(discussion)}"
                    )
                ]
            )
        )

    async def _topic_status(self, event: AstrMessageEvent) -> None:
        task = await self._get_active_topic_task(event)
        if task is None:
            await event.send(MessageChain([Plain("当前群没有进行中的灰度话题。")]))
            return
        discussion = await self._topic_discussion_snapshot(task.task_id)
        rollcall = self._topic_rollcall.get(task.task_id, {})
        checked_in = rollcall.get("checked_in", {})
        await event.send(
            MessageChain(
                [
                    Plain(
                        "当前灰度话题：\n"
                        f"- topic_id: {task.task_id[:8]}\n"
                        f"- task_id: {task.task_id}\n"
                        f"- status: {task.status}\n"
                        f"- title: {task.title}\n"
                        f"- collected_messages: {len(discussion)}\n"
                        f"- rollcall_checked_in: {len(checked_in)}"
                    )
                ]
            )
        )

    async def _topic_intro(self, event: AstrMessageEvent) -> None:
        await event.send(MessageChain([Plain(self._grey_topic_intro_message())]))

    def _grey_topic_intro_message(self) -> str:
        return (
            "【灰度测试说明】\n"
            "本群用于验证“话题讨论 + 后台深挖 + 满意度闭环”的协作流程。\n\n"
            "一、入群准备\n"
            "1. 请每位成员主动把群名片改成：姓名-部门-角色，例如“蔡挺-市场部-负责人”。\n"
            "2. 群名片用于推广 1 号识别发言角色、统计点名和整理讨论，不改名片会影响测试记录准确性。\n"
            "3. QQ 群和飞书群默认先禁言 10 分钟，用于成员进群、改名片和阅读说明。\n"
            "4. 禁言解除后，群管理会发起点名；请每个人回复 1 或 到，确认在场后再开始测试。\n\n"
            "参与角色：\n"
            "1. 老板/发起人：发布本轮话题，判断最终方向是否满意。\n"
            "2. 部门负责人：补充业务背景、约束条件、判断标准和风险点。\n"
            "3. 员工/评审成员：直接提出疑问、反例、补充资料和不满意点。\n"
            "4. 业务 bot（推广 1 号）：记录群内讨论；需要深挖时把当前话题交给后台 Hermes 处理。\n\n"
            "二、基础指令\n"
            "- 发布话题：/topic new <本轮要讨论的问题>\n"
            "- 发起点名：/topic rollcall start\n"
            "- 查看点名：/topic rollcall status\n"
            "- 结束点名：/topic rollcall end\n"
            "- 后台深挖：/topic deep <为什么还不满意或需要补充什么>\n"
            "- 查看话题：/topic status\n"
            "- 查看蒸馏摘要：/topic distill\n"
            "- 重发说明：/topic intro\n"
            "- 结束本轮：/topic close <最终结论>\n\n"
            "三、自然语言范围\n"
            "大家可以直接用正常工作语言讨论，例如：\n"
            "- 我觉得这个方案不落地，因为……\n"
            "- 这里缺少预算/时间/负责人/风险判断。\n"
            "- 老板要看的结论应该是……\n"
            "- 员工执行时可能会卡在……\n"
            "- 这个点需要 Hermes 后台继续深挖。\n\n"
            "四、测试规则\n"
            "1. 群内只保留推广 1 号一个业务 bot，其他成员都按真人身份发言。\n"
            "2. 不需要为了机器人改变说话方式；请像真实会议一样提出问题、分歧和不满意点。\n"
            "3. 如果只是继续讨论，直接发自然语言；如果明确要后台研究，请使用 /topic deep。\n"
            "4. 只有确认过的业务事实、流程、标准话术和产品资料会作为知识库候选。"
        )

    async def _topic_rollcall_command(
        self,
        event: AstrMessageEvent,
        body: str,
    ) -> None:
        task = await self._get_active_topic_task(event)
        if task is None:
            await event.send(MessageChain([Plain("当前群没有进行中的灰度话题。")]))
            return

        action = (body or "start").strip().lower()
        if action in ("start", "开始", ""):
            self._topic_rollcall[task.task_id] = {
                "active": True,
                "checked_in": {},
                "started_by": event.get_sender_id(),
            }
            await self._append_topic_event(
                task.task_id,
                "topic_rollcall_started",
                {
                    "started_by": event.get_sender_id(),
                    "session_id": event.unified_msg_origin,
                },
            )
            await event.send(
                MessageChain(
                    [
                        Plain(
                            "【点名开始】\n"
                            "禁言解除后，请所有参与灰度测试的成员回复：1 或 到。\n"
                            "推广 1 号会自动登记，登记完成后再开始正式测试。"
                        )
                    ]
                )
            )
            return

        if action in ("status", "状态"):
            rollcall = self._topic_rollcall.get(task.task_id, {})
            checked_in = rollcall.get("checked_in", {})
            lines = [
                "【点名状态】",
                f"- topic_id: {task.task_id[:8]}",
                f"- active: {bool(rollcall.get('active'))}",
                f"- checked_in: {len(checked_in)}",
            ]
            for name in list(checked_in.values())[:20]:
                lines.append(f"- {name}")
            await event.send(MessageChain([Plain("\n".join(lines))]))
            return

        if action in ("end", "stop", "结束", "停止"):
            rollcall = self._topic_rollcall.setdefault(
                task.task_id,
                {"checked_in": {}},
            )
            rollcall["active"] = False
            checked_in = rollcall.get("checked_in", {})
            await self._append_topic_event(
                task.task_id,
                "topic_rollcall_finished",
                {
                    "finished_by": event.get_sender_id(),
                    "checked_in_count": len(checked_in),
                    "checked_in": checked_in,
                },
            )
            await event.send(
                MessageChain(
                    [
                        Plain(
                            "【点名结束】\n"
                            f"已登记 {len(checked_in)} 人。可以开始本轮灰度测试。"
                        )
                    ]
                )
            )
            return

        await event.send(
            MessageChain(
                [
                    Plain(
                        "点名指令：\n"
                        "- /topic rollcall start\n"
                        "- /topic rollcall status\n"
                        "- /topic rollcall end"
                    )
                ]
            )
        )

    async def _handle_rollcall_reply(
        self,
        event: AstrMessageEvent,
        user_id: str,
        text: str,
    ) -> bool:
        if text.strip().lower() not in ("1", "到"):
            return False
        task = await self._get_active_topic_task(event)
        if task is None:
            return False
        rollcall = self._topic_rollcall.get(task.task_id)
        if not rollcall or not rollcall.get("active"):
            return False

        checked_in = rollcall.setdefault("checked_in", {})
        sender_name = event.get_sender_name() or user_id
        checked_in[user_id] = sender_name
        await self._append_topic_event(
            task.task_id,
            "topic_rollcall_checkin",
            {
                "sender_id": user_id,
                "sender_name": sender_name,
                "session_id": event.unified_msg_origin,
            },
        )
        await event.send(MessageChain([Plain(f"已登记：{sender_name}")]))
        return True

    async def _topic_distill(self, event: AstrMessageEvent) -> None:
        task = await self._get_active_topic_task(event)
        if task is None:
            await event.send(MessageChain([Plain("当前群没有进行中的灰度话题。")]))
            return
        discussion = await self._topic_discussion_snapshot(task.task_id)
        distillation = self._distill_grey_topic(task, discussion)
        await self._append_topic_distillation(task.task_id, distillation)
        await event.send(MessageChain([Plain(self._format_distillation(distillation))]))

    async def _topic_close(
        self,
        event: AstrMessageEvent,
        user_id: str,
        summary: str,
    ) -> None:
        engine = self.context.harness_engine
        if engine is None:
            await event.send(MessageChain([Plain("Harness 引擎未初始化。")]))
            return
        task = await self._get_active_topic_task(event)
        if task is None:
            await event.send(MessageChain([Plain("当前群没有进行中的灰度话题。")]))
            return
        discussion = await self._topic_discussion_snapshot(task.task_id)
        distillation = self._distill_grey_topic(
            task,
            discussion,
            final_summary=summary.strip(),
        )
        result = {
            "summary": summary.strip() or "灰度话题已由管理员关闭。",
            "source": "grey_topic_review",
            "closed_by": user_id,
            "discussion_count": len(discussion),
            "discussion": discussion,
            "distillation": distillation,
        }
        await self._append_topic_distillation(task.task_id, distillation)
        await engine.complete_task(task.task_id, result=result)
        self._topic_discussion_cache.pop(task.task_id, None)
        await event.send(
            MessageChain(
                [
                    Plain(
                        f"灰度话题已关闭：{task.task_id[:8]}\n"
                        "讨论、结果和蒸馏摘要已写入 Harness 任务记录。\n\n"
                        f"{self._format_distillation(distillation)}"
                    )
                ]
            )
        )

    async def _record_topic_discussion(
        self,
        event: AstrMessageEvent,
        user_id: str,
        message_text: str,
    ) -> None:
        task = await self._get_active_topic_task(event)
        if task is None:
            return

        item = {
            "sender_id": user_id,
            "sender_name": event.get_sender_name() or user_id,
            "message": message_text.strip()[:1200],
            "platform_id": event.get_platform_id(),
            "session_id": event.unified_msg_origin,
        }
        self._topic_discussion_cache[task.task_id].append(item)
        try:
            await self.context.harness_engine.append_trace(
                task.task_id,
                "topic_discussion_message",
                item,
            )
        except Exception as exc:
            logger.debug("[HermesBridge] 记录灰度话题讨论失败：%s", exc)

    async def _get_active_topic_task(self, event: AstrMessageEvent):
        store = getattr(self.context, "harness_store", None)
        if store is None:
            engine = getattr(self.context, "harness_engine", None)
            store = getattr(engine, "store", None)
        if store is None:
            return None

        statuses = tuple(
            status
            for status in (
                "pending",
                "in_progress",
                "blocked",
                "review_required",
            )
            if status not in HARNESS_TERMINAL_STATUSES
        )
        tasks = await store.list_tasks_for_session(
            event.unified_msg_origin,
            limit=10,
            statuses=statuses,
        )
        for task in tasks:
            if task.payload.get("source") == "grey_topic":
                return task
        return None

    async def _topic_discussion_snapshot(self, task_id: str) -> list[dict]:
        cached = list(self._topic_discussion_cache.get(task_id, []))
        if cached:
            return cached[-self.topic_discussion_limit :]

        store = getattr(self.context, "harness_store", None)
        if store is None:
            engine = getattr(self.context, "harness_engine", None)
            store = getattr(engine, "store", None)
        if store is None:
            return []
        try:
            events = await store.list_events(task_id)
        except Exception:
            return []
        discussion = [
            event.payload
            for event in events
            if event.event_type == "topic_discussion_message"
        ]
        return discussion[-self.topic_discussion_limit :]

    async def _append_topic_distillation(
        self,
        task_id: str,
        distillation: dict,
    ) -> None:
        if not self.topic_distill_enabled:
            return
        engine = getattr(self.context, "harness_engine", None)
        if engine is None:
            return
        try:
            await engine.append_trace(
                task_id,
                "topic_distillation_snapshot",
                distillation,
            )
        except Exception as exc:
            logger.debug("[HermesBridge] 记录灰度蒸馏摘要失败：%s", exc)

    async def _append_topic_event(
        self,
        task_id: str,
        event_type: str,
        payload: dict,
    ) -> None:
        engine = getattr(self.context, "harness_engine", None)
        if engine is None:
            return
        try:
            await engine.append_trace(task_id, event_type, payload)
        except Exception as exc:
            logger.debug("[HermesBridge] 记录灰度事件失败 %s：%s", event_type, exc)

    def _distill_grey_topic(
        self,
        task,
        discussion: list[dict],
        *,
        trigger_reason: str = "",
        final_summary: str = "",
    ) -> dict:
        if not self.topic_distill_enabled:
            return {}

        buckets = {
            "boss_success_criteria": [],
            "department_constraints": [],
            "employee_questions": [],
            "dissatisfaction_signals": [],
            "knowledge_candidates": [],
            "bot_role_hints": [],
        }
        role_counts: dict[str, int] = {}

        for item in discussion:
            message = str(item.get("message") or "").strip()
            if not message:
                continue
            sender_name = str(
                item.get("sender_name") or item.get("sender_id") or "unknown"
            )
            role_counts[sender_name] = role_counts.get(sender_name, 0) + 1
            compact = " ".join(message.split())[:220]
            lowered = compact.lower()

            if self._contains_any(
                compact,
                (
                    "目标",
                    "满意",
                    "不满意",
                    "标准",
                    "结果",
                    "老板",
                    "老总",
                    "判断",
                    "要的是",
                ),
            ):
                buckets["boss_success_criteria"].append(f"{sender_name}: {compact}")
            if self._contains_any(
                compact,
                (
                    "预算",
                    "资源",
                    "人手",
                    "时间",
                    "周期",
                    "风险",
                    "合规",
                    "审批",
                    "部门",
                    "负责人",
                    "限制",
                ),
            ):
                buckets["department_constraints"].append(f"{sender_name}: {compact}")
            if (
                "?" in compact
                or "？" in compact
                or self._contains_any(
                    compact,
                    (
                        "为什么",
                        "怎么",
                        "如何",
                        "是否",
                        "能不能",
                        "是不是",
                        "哪里",
                        "谁来",
                        "多久",
                    ),
                )
            ):
                buckets["employee_questions"].append(f"{sender_name}: {compact}")
            if self._contains_any(
                compact,
                (
                    "不满意",
                    "不够",
                    "不行",
                    "不对",
                    "不落地",
                    "太空",
                    "看不懂",
                    "没解决",
                    "继续深挖",
                    "再查",
                ),
            ):
                buckets["dissatisfaction_signals"].append(f"{sender_name}: {compact}")
            if self._contains_any(
                compact,
                (
                    "流程",
                    "规则",
                    "标准",
                    "资料",
                    "文档",
                    "话术",
                    "案例",
                    "客户",
                    "产品",
                    "知识库",
                ),
            ):
                buckets["knowledge_candidates"].append(f"{sender_name}: {compact}")
            if self._contains_any(
                compact,
                (
                    "机器人",
                    "bot",
                    "回复",
                    "语气",
                    "格式",
                    "别",
                    "不要",
                    "需要先",
                    "应该",
                ),
            ):
                buckets["bot_role_hints"].append(f"{sender_name}: {compact}")

            if "老板" in compact or "老总" in compact:
                buckets["bot_role_hints"].append(
                    f"{sender_name}: 老板相关内容需要结论先行，并明确判断标准。"
                )
            if "员工" in compact:
                buckets["bot_role_hints"].append(
                    f"{sender_name}: 员工相关内容需要给出可执行步骤，减少抽象表述。"
                )
            if "hermes" in lowered or "深挖" in compact:
                buckets["bot_role_hints"].append(
                    f"{sender_name}: 深挖请求应带上话题、讨论分歧和不满意原因。"
                )

        for key, values in buckets.items():
            buckets[key] = self._dedupe_keep_order(values, limit=6)

        return {
            "topic_id": task.task_id,
            "title": getattr(task, "title", ""),
            "trigger_reason": trigger_reason,
            "final_summary": final_summary,
            "discussion_count": len(discussion),
            "speaker_count": len(role_counts),
            "speaker_activity": dict(
                sorted(role_counts.items(), key=lambda item: item[1], reverse=True)[:8]
            ),
            **buckets,
            "knowledge_policy": (
                "仅将已确认的业务事实、流程、标准话术和产品资料沉淀进正式知识库；"
                "偏好、疑问和不满意信号先作为灰度画像与路由规则使用。"
            ),
        }

    def _format_distillation(self, distillation: dict) -> str:
        if not distillation:
            return "【灰度蒸馏摘要】当前未启用对话蒸馏。"

        def render_items(title: str, key: str) -> list[str]:
            values = distillation.get(key) or []
            if not values:
                return [f"{title}：暂无明确样本"]
            return [f"{title}："] + [f"- {value}" for value in values[:4]]

        lines = [
            "【灰度蒸馏摘要】",
            f"话题：{distillation.get('title') or distillation.get('topic_id', '')}",
            f"讨论消息：{distillation.get('discussion_count', 0)} 条；参与者：{distillation.get('speaker_count', 0)} 人",
            "",
            *render_items("老板/发起人判断标准", "boss_success_criteria"),
            "",
            *render_items("部门负责人约束", "department_constraints"),
            "",
            *render_items("员工疑问/阻力", "employee_questions"),
            "",
            *render_items("不满意/需深挖信号", "dissatisfaction_signals"),
            "",
            *render_items("知识库候选", "knowledge_candidates"),
            "",
            *render_items("推广 1 号角色修正", "bot_role_hints"),
            "",
            f"知识库策略：{distillation.get('knowledge_policy', '')}",
        ]
        return "\n".join(lines).strip()

    def _contains_any(self, text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _dedupe_keep_order(self, values: list[str], *, limit: int) -> list[str]:
        seen = set()
        result = []
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
            if len(result) >= limit:
                break
        return result

    async def _get_or_create_current_conversation_id(
        self,
        event: AstrMessageEvent,
    ) -> str:
        conv_mgr = self.context.conversation_manager
        umo = event.unified_msg_origin
        cid = await conv_mgr.get_curr_conversation_id(umo)
        if cid:
            return cid
        return await conv_mgr.new_conversation(umo, event.get_platform_id())

    def _get_or_create_session(self, user_id: str, platform: PlatformType) -> str:
        pu = PlatformUser(platform=platform, user_id=user_id)
        return self.session_router.get_or_create_session(pu)

    async def shutdown(self):
        logger.info("[HermesBridge] 插件已关闭")
