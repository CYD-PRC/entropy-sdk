"""
Utility Gate（论文 Definitions 2–3，Theorem 2）

门是唯一调度通道：动作被执行当且仅当 Gate=1，即 U(s,a) >= theta。
本 SDK 不内置任何效用函数——U 必须由使用者按领域注入。
未注入效用函数时构造即报错（fail-closed，无 fail-open 开关）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class UtilityFunction(Protocol):
    """效用函数协议：U: S × A → R。

    推荐形态（论文 §4）：U(s,a) = α·Δtask + β·safety − γ·cost，
    多智能体场景可把传感器熵项 H_i 折进 cost（论文 §6.1）。
    """

    def __call__(self, state: Any, action: Any) -> float: ...


@dataclass(frozen=True)
class GateDecision:
    """一次门判定的完整记录（审计用）。"""

    admitted: bool
    utility: float
    theta: float
    reason: str = ""
    meta: dict = field(default_factory=dict)


class UtilityGate:
    """二元效用门：Gate(s,a) = 1 iff U(s,a) >= θ。"""

    def __init__(self, utility: UtilityFunction | Callable[[Any, Any], float], theta: float = 0.0):
        if utility is None:
            raise ValueError(
                "UtilityGate requires an explicit utility function. "
                "There is no fail-open mode: the gate is the sole dispatch channel."
            )
        if theta < 0:
            raise ValueError("theta must be >= 0 (paper Definition 3)")
        self._utility = utility
        self.theta = float(theta)

    def evaluate(self, state: Any, action: Any) -> GateDecision:
        # FIX-2：效用函数异常视同 U=−∞ 拒绝（fail-closed），不穿透 step()；
        # meta 载明错误类型，由 runtime 落 gate_error 审计（与 execute 异常分属）。
        try:
            u = float(self._utility(state, action))
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            return GateDecision(
                admitted=False,
                utility=float("-inf"),
                theta=self.theta,
                reason=f"gate_error: utility raised {err} (treated as U=-inf)",
                meta={"gate_error": err},
            )
        admitted = u >= self.theta
        return GateDecision(
            admitted=admitted,
            utility=u,
            theta=self.theta,
            reason="" if admitted else f"U={u:.4f} < theta={self.theta:.4f}",
        )
