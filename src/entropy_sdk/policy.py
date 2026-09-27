"""
Gear 转移策略（论文 §4 Gear state machine）

慢升快降（earned autonomy）：
- 升档：σ < σ_low 且连续 h 个干净周期 → 升一档
- 降档：σ > σ_high 或 ϵ=1 → 立即降一档
- 否则：保持
"""
from __future__ import annotations

import math

from dataclasses import dataclass

from .gear import Gear
from .state import RuntimeState


@dataclass(frozen=True)
class GearPolicy:
    sigma_low: float = 0.3    # 升档门槛
    sigma_high: float = 1.0   # 降档门槛
    patience: int = 3         # h：升档所需连续干净周期
    sigma_decay: float = 0.1  # δ：动作被接受时 σ 的衰减
    sigma_step: float = 0.1   # Δσ：fallback 失败时 σ 的增量

    def __post_init__(self):
        # FIX-3a + FIX2-2：非法参数构造即抛（fail-closed）
        # ——finite 校验：patience=NaN 会静默锁死 G0（clean_streak>=NaN 恒 False），
        #   patience=1.5 会静默变 2；σ 族 NaN/±inf 同理拒收
        for name in ("sigma_low", "sigma_high", "sigma_decay", "sigma_step"):
            v = getattr(self, name)
            if not (isinstance(v, (int, float)) and math.isfinite(v)):
                raise ValueError(f"{name} must be finite, got {v!r}")
        if isinstance(self.patience, bool) or not (
            isinstance(self.patience, int)
            or (isinstance(self.patience, float) and self.patience.is_integer())
        ):
            raise ValueError(f"patience must be an integer, got {self.patience!r}")
        if self.patience < 1:
            raise ValueError("patience must be >= 1")
        if self.sigma_decay < 0:
            raise ValueError("sigma_decay must be >= 0")
        if self.sigma_step < 0:
            raise ValueError("sigma_step must be >= 0")
        if not self.sigma_low < self.sigma_high:
            raise ValueError("sigma_low must be < sigma_high")

    def next_gear(self, state: RuntimeState) -> Gear:
        g = state.gear
        if state.sigma > self.sigma_high or state.error:
            return Gear(max(int(g) - 1, int(Gear.OBSERVE)))
        if state.sigma < self.sigma_low and state.clean_streak >= self.patience:
            return Gear(min(int(g) + 1, int(Gear.INTEGRATE)))
        return g
