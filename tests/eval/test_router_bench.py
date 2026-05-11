"""Router Benchmark v0 — Phase R0.5

衡量 IntentRouter **纯规则层**的分类准确率。LLM fallback 关闭，
让基线干净、可重复；后续 R2 嵌入分类器 / R3 LLM-judge 的贡献能被独立度量。

产物：
- ``data/router_bench/latest.md``    本次详细报告（markdown）
- ``data/router_bench/history.jsonl`` 历史趋势（每跑一次追加一行）

CI 行为：
- 整体准确率 < BASELINE_ACCURACY → 测试失败
- 任意 ``category`` 子集准确率 < CATEGORY_BASELINE → 测试失败
"""

from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path

import pytest
import yaml

from astrbot.core.router import IntentRouter

# ── 配置 ──────────────────────────────────────────────────────────────────────

_BENCH_PATH = Path(__file__).parent / "router_bench_v0.yaml"
_ROUTER_CONFIG = (
    Path(__file__).resolve().parents[2] / "astrbot" / "core" / "router_config.yaml"
)
_REPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "router_bench"

# Phase R0.5 基线。首次跑 100% 通过，锁紧到 95% 留 2 条容差；
# 后续 v1 数据集（加入 paraphrase / adversarial / multi-intent）出来后再考虑下调。
BASELINE_ACCURACY = float(os.environ.get("ROUTER_BENCH_BASELINE", "0.95"))
CATEGORY_BASELINE = float(os.environ.get("ROUTER_BENCH_CAT_BASELINE", "0.85"))


# ── 工具 ──────────────────────────────────────────────────────────────────────


def _matches(expect: dict, intent) -> bool:
    if expect.get("category") and expect["category"] != intent.category:
        return False
    if "intent_type" in expect and expect["intent_type"] != intent.intent_type:
        return False
    if "workflow_kind" in expect and expect["workflow_kind"] != intent.workflow_kind:
        return False
    if "skill_name" in expect and expect["skill_name"] != intent.skill_name:
        return False
    return True


def _format_failure(sample: dict, intent) -> str:
    actual = {
        "category": intent.category,
        "intent_type": intent.intent_type,
        "workflow_kind": intent.workflow_kind,
        "skill_name": intent.skill_name,
        "confidence": round(intent.confidence, 3),
    }
    return f"- `{sample['id']}` | msg=`{sample['message']!r}` | expect={sample['expect']} | actual={actual}"


def _write_report(
    *,
    samples: list[dict],
    intents: list,
    correct_flags: list[bool],
    latencies_ms: list[float],
) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)

    total = len(samples)
    correct = sum(correct_flags)
    accuracy = correct / total if total else 0.0

    # per-category 统计
    cats: dict[str, list[bool]] = {}
    for sample, flag in zip(samples, correct_flags):
        cat = sample["expect"].get("category", "?")
        cats.setdefault(cat, []).append(flag)

    p50 = statistics.median(latencies_ms) if latencies_ms else 0.0
    p95 = (
        sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1]
        if len(latencies_ms) >= 20
        else max(latencies_ms or [0.0])
    )

    # ── markdown 报告 ────────────────────────────────────────────────────────
    lines: list[str] = []
    lines.append("# Router Benchmark v0 — Latest Run")
    lines.append("")
    lines.append(f"- 运行时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 样本总数: **{total}**")
    lines.append(f"- 整体准确率: **{accuracy:.2%}** (baseline {BASELINE_ACCURACY:.0%})")
    lines.append(f"- 延迟 P50 / P95: {p50:.2f}ms / {p95:.2f}ms")
    lines.append("")
    lines.append("## 分类别准确率")
    lines.append("")
    lines.append("| category | 命中 / 总数 | 准确率 |")
    lines.append("|----------|------------|--------|")
    for cat, flags in sorted(cats.items()):
        c, t = sum(flags), len(flags)
        lines.append(f"| {cat} | {c} / {t} | {c / t:.0%} |")
    lines.append("")

    # 错分 case
    failures: list[str] = []
    for sample, intent, flag in zip(samples, intents, correct_flags):
        if not flag:
            failures.append(_format_failure(sample, intent))
    if failures:
        lines.append(f"## 错分样本 ({len(failures)} 条)")
        lines.append("")
        lines.extend(failures)
    else:
        lines.append("## 错分样本：无 🎉")
    lines.append("")

    (_REPORT_DIR / "latest.md").write_text("\n".join(lines), encoding="utf-8")

    # ── history.jsonl ─────────────────────────────────────────────────────────
    history_entry = {
        "ts": time.time(),
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "category_accuracy": {
            cat: round(sum(flags) / len(flags), 4) for cat, flags in cats.items()
        },
        "latency_p50_ms": round(p50, 3),
        "latency_p95_ms": round(p95, 3),
        "baseline": BASELINE_ACCURACY,
        "failures": [s["id"] for s, flag in zip(samples, correct_flags) if not flag],
    }
    with open(_REPORT_DIR / "history.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def samples() -> list[dict]:
    raw = yaml.safe_load(_BENCH_PATH.read_text(encoding="utf-8")) or []
    assert isinstance(raw, list), "router_bench_v0.yaml 应为 list"
    return raw


@pytest.fixture(scope="module")
def router() -> IntentRouter:
    return IntentRouter.from_yaml(_ROUTER_CONFIG, llm_provider=None)


# ── 主测试：跑全量 + 落报告 + 卡阈值 ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_router_bench_v0_accuracy(router: IntentRouter, samples: list[dict]):
    """整体准确率必须 ≥ BASELINE_ACCURACY，否则视为回归。"""
    intents = []
    correct_flags: list[bool] = []
    latencies_ms: list[float] = []

    for sample in samples:
        start = time.perf_counter()
        intent = await router.classify(sample["message"], {})
        latency_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(latency_ms)
        intents.append(intent)
        correct_flags.append(_matches(sample["expect"], intent))

    _write_report(
        samples=samples,
        intents=intents,
        correct_flags=correct_flags,
        latencies_ms=latencies_ms,
    )

    total = len(samples)
    correct = sum(correct_flags)
    accuracy = correct / total if total else 0.0

    # per-category 子集阈值
    cats: dict[str, list[bool]] = {}
    for sample, flag in zip(samples, correct_flags):
        cat = sample["expect"].get("category", "?")
        cats.setdefault(cat, []).append(flag)
    for cat, flags in cats.items():
        ca = sum(flags) / len(flags)
        assert ca >= CATEGORY_BASELINE, (
            f"Category {cat!r} 准确率 {ca:.2%} 低于 baseline {CATEGORY_BASELINE:.0%}"
        )

    assert accuracy >= BASELINE_ACCURACY, (
        f"Router 整体准确率 {accuracy:.2%} 低于 baseline {BASELINE_ACCURACY:.0%}. "
        f"详见 data/router_bench/latest.md"
    )


def test_router_bench_dataset_well_formed(samples: list[dict]):
    """数据集结构本身合规：id 唯一、message 字符串、expect.category 必填。"""
    ids = [s["id"] for s in samples]
    assert len(ids) == len(set(ids)), "样本 id 不应重复"
    for s in samples:
        assert isinstance(s.get("message"), str), f"{s['id']}: message 必须是字符串"
        assert s.get("expect", {}).get("category") in (
            "task",
            "skill",
            "conversation",
        ), f"{s['id']}: expect.category 必须是 task/skill/conversation"
