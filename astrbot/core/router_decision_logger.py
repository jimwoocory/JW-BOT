"""Router 决策事件的 JSONL 落盘记录器（Phase R0.2）。

设计目标：
- 每条 RouterStage.route 决策落一行 JSON，包含分类结果、延迟、是否走 LLM 等。
- 单文件 + 单备份的环形轮转（默认 10MB），避免无限增长。
- async 安全：内部 asyncio.Lock 串行化写入。
- 失败容错：任何写入异常不得阻断路由主流程。

下游消费者：
- R0.5 router benchmark：抽取历史样本作为 ground-truth 候选。
- R1.6 clarify 用户选项回写：扩展同一文件 schema。
- R2.4 嵌入分类器持续学习：把 user-confirmed 决策训练 centroid。
- R4 Dashboard：滑动窗口准确率 / clarify rate / 漂移热力。
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10MB


class RouterDecisionLogger:
    """Append-only JSONL logger with single-backup rotation."""

    def __init__(
        self,
        path: Path | str,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self._lock = asyncio.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def backup_path(self) -> Path:
        return self.path.with_name(self.path.name + ".1")

    async def log(self, record: dict[str, Any]) -> None:
        """写入一条决策记录。任何 I/O 异常被吞掉以保护路由主流程。"""
        try:
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        except (TypeError, ValueError):
            # 不可序列化的字段直接放弃这条记录
            return
        encoded = line.encode("utf-8")

        async with self._lock:
            try:
                await asyncio.to_thread(self._write_with_rotation, encoded)
            except OSError:
                # 落盘失败不影响主流程
                return

    def _write_with_rotation(self, encoded: bytes) -> None:
        """同步实现：必要时轮转，然后追加写入。"""
        try:
            current_size = self.path.stat().st_size
        except FileNotFoundError:
            current_size = 0

        if current_size + len(encoded) > self.max_bytes and current_size > 0:
            backup = self.backup_path
            try:
                if backup.exists():
                    backup.unlink()
                self.path.rename(backup)
            except OSError:
                # 轮转失败就放弃轮转、继续直接追加（最坏情况文件略微超限）
                pass

        with open(self.path, "ab") as f:
            f.write(encoded)


def build_decision_record(
    *,
    message: str,
    umo: str,
    platform_id: str,
    category: str,
    intent_type: str,
    confidence: float,
    workflow_kind: str | None,
    skill_name: str | None,
    matched_by: str,
    llm_called: bool,
    fallback_threshold: float,
    latency_ms: float,
    span_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """统一构造 RouterDecisionLogger 写入的 record dict。

    decision_zone 当前是 auto / fallback 二段；Phase R1 引入 clarify 后再扩展。
    """
    if matched_by == "rule" and confidence >= fallback_threshold:
        decision_zone = "auto"
    elif matched_by == "llm" and confidence >= fallback_threshold:
        decision_zone = "auto"
    else:
        decision_zone = "fallback"

    record: dict[str, Any] = {
        "ts": time.time(),
        "umo": umo,
        "platform_id": platform_id,
        "msg_preview": (message or "").strip()[:200],
        "category": category,
        "intent_type": intent_type,
        "confidence": round(float(confidence), 4),
        "workflow_kind": workflow_kind,
        "skill_name": skill_name,
        "matched_by": matched_by,
        "llm_called": llm_called,
        "decision_zone": decision_zone,
        "latency_ms": round(float(latency_ms), 3),
    }
    if span_id:
        record["span_id"] = span_id
    if extra:
        record["extra"] = extra
    return record


__all__ = [
    "DEFAULT_MAX_BYTES",
    "RouterDecisionLogger",
    "build_decision_record",
]
