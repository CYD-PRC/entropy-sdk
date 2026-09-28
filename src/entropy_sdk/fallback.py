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

import math

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class FallbackConfig:
    max_alternatives: int = 3      # k：每档最多尝试的备选数
    max_consecutive_rejections: int = 5  # m：连续拒绝上限，触发 G0 挂起

    def __post_init__(self):
        # FIX7-2：整数值 float 归一化（构造契约 == 执行契约）——
        # 3.0 通过整数性校验后字段归一为 int 3，runtime 的 range() 不再炸；
        # 非整数值 float（1.5）仍在下方校验拒绝。
        for name in ("max_alternatives", "max_consecutive_rejections"):
            v = getattr(self, name)
            if isinstance(v, float) and v.is_integer():
                object.__setattr__(self, name, int(v))
        # FIX-3b + FIX2-2 + FIX2-3：构造期校验（fail-closed）
        # max_alternatives：0 合法（关闭 fallback 的显式语义，v0.1.2 恢复；
        # v0.1 的 >=1 校验误杀了该意图——CHANGELOG 标注破坏性恢复）；上界 100
        # 防 10**9 级每周期巨大循环。两参数均须有限整数。
        for name in ("max_alternatives", "max_consecutive_rejections"):
            v = getattr(self, name)
            if isinstance(v, bool) or not (
                isinstance(v, int)
                or (isinstance(v, float) and math.isfinite(v) and v.is_integer())
            ):
                raise ValueError(f"{name} must be a finite integer, got {v!r}")
        if not 0 <= self.max_alternatives <= 100:
            raise ValueError("max_alternatives must be in [0, 100] (0 = fallback off)")
        if self.max_consecutive_rejections < 1:
            raise ValueError("max_consecutive_rejections must be >= 1")


# 备选生成器签名：(state, rejected_action, attempt_index) -> alternative action | None
AlternativeProposer = Callable[[Any, Any, int], Any | None]
