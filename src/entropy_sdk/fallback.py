"""
事件驱动 Fallback（论文 §4，Theorem 4）

拒绝后的恢复路径：
1. 记录拒绝，σ 上升；
2. 由 proposer 生成备选动作 a′，重新过门；
3. k 次备选全败 → 降一档，下周期待定；
4. m 次连续拒绝 → 降到 G0 并挂起，等待人工复核。

Theorem 4 保证：任何错误态至多 |G|−1=4 步降到 G0，
G0 的只读动作平凡地满足 U ≥ 0 —— 系统永远有恢复路径，不需要重启。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FallbackConfig:
    max_alternatives: int = 3      # k：每档最多尝试的备选数
    max_consecutive_rejections: int = 5  # m：连续拒绝上限，触发 G0 挂起


# 备选生成器签名：(state, rejected_action, attempt_index) -> alternative action | None
AlternativeProposer = Callable[[Any, Any, int], Any | None]
