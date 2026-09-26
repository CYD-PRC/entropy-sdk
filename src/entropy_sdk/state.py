"""
运行时状态 ρ=(g, σ, ϵ) 与 append-only 审计链（论文 Definition 4）

审计链是 SDK 的一等公民：每次门判定、换挡、fallback、挂起都落一条 JSONL。
这条链就是论文 Section 5/8 所需的实证数据来源（gate 接受率、gear 转移直方图）。
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .gear import Gear


@dataclass
class RuntimeState:
    """单 agent 运行时状态（环境状态 s 由使用者持有，此处只保留控制量）。"""

    gear: Gear = Gear.OBSERVE
    sigma: float = 0.0          # σ：累积不稳定度
    error: bool = False         # ϵ：错误标志
    cycle: int = 0              # t：离散周期计数
    clean_streak: int = 0       # 连续干净周期数（升档耐心计数）
    consecutive_rejections: int = 0
    suspended: bool = False     # m 次连续拒绝后挂起，等待人工复核

    def snapshot(self) -> dict:
        d = asdict(self)
        d["gear"] = int(self.gear)
        d["gear_label"] = self.gear.label
        return d


class AuditLog:
    """append-only JSONL 审计链。只追加，不修改，不落盘失败则抛错（fail-closed）。"""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self._buffer: list[dict] = []
        self.corrupt_lines: int = 0  # FIX-5c：最近一次读盘跳过的坏行数

    def record(self, kind: str, **fields: Any) -> dict:
        # FIX-5d：非有限浮点（NaN/Inf）消毒为 null + 同名字段加 _nonfinite 标记，
        # 保证 JSONL 对严格解析器合法（门对 NaN 效用的 fail-closed 行为不变）
        clean = {}
        for k, v in fields.items():
            if isinstance(v, float) and not math.isfinite(v):
                clean[k] = None
                clean[f"{k}_nonfinite"] = True
            else:
                clean[k] = v
        entry = {"ts": time.time(), "kind": kind, **clean}
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        else:
            self._buffer.append(entry)
        return entry

    @property
    def entries(self) -> list[dict]:
        # FIX-5b：文件模式与 metrics 同语义——读盘返回（README 主推路径不再恒空）
        if self.path and self.path.exists():
            return list(self._iter_all())
        return list(self._buffer)

    def gear_histogram(self) -> dict[int, int]:
        """gear 转移直方图（Theorem 3 最终镇定的经验证据）。"""
        hist: dict[int, int] = {}
        for e in self._iter_all():
            if e.get("kind") == "gear_transition":
                hist[e["to"]] = hist.get(e["to"], 0) + 1
        return hist

    def gate_acceptance_rate(self) -> float | None:
        """门接受率（Theorem 1 关键假设 p1 >= p3 的经验观测口径）。"""
        decisions = [e for e in self._iter_all() if e.get("kind") == "gate_decision"]
        if not decisions:
            return None
        return sum(1 for e in decisions if e["admitted"]) / len(decisions)

    def _iter_all(self):
        if self.path and self.path.exists():
            self.corrupt_lines = 0
            with self.path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            # FIX-5c：坏行跳过并计数，不崩（append-only 链的
                            # 半截写入/磁盘伤不应炸掉整个读面）
                            self.corrupt_lines += 1
        else:
            yield from self._buffer
