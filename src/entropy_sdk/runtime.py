"""
EntropyRuntime 控制循环（论文 §4 Algorithm 1）

每周期四阶段：观察与档位评估 → 动作生成 → 效用门 → 执行与反馈。
门是唯一调度通道：被拒绝的动作绝不执行（Theorem 2）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .fallback import AlternativeProposer, FallbackConfig
from .gate import GateDecision, UtilityFunction, UtilityGate
from .gear import Gear
from .policy import GearPolicy
from .state import AuditLog, RuntimeState


def _safe_gear(value: Any) -> Gear | None:
    """把调用方声明的 required_gear 收敛成合法 Gear；非法值返回 None（FIX-4）。

    required_gear 是调用方声明契约（attestation）——标签不可信时
    fail-closed：视同「不允许」，走档位前置闸拒绝路径，不抛栈穿透。
    """
    try:
        return Gear(int(value))
    except (TypeError, ValueError):
        return None


@dataclass
class CycleResult:
    """单周期结果。"""

    executed: bool
    action: Any
    gate: GateDecision | None
    gear_before: Gear
    gear_after: Gear
    used_fallback: bool = False
    suspended: bool = False
    result: Any = None
    error: str | None = None


class EntropyRuntime:
    """可嵌入的档位安全控制层。

    用法（最小闭环）::

        runtime = EntropyRuntime(utility=my_utility, theta=0.15)
        result = runtime.step(
            state=my_state,
            action=agent_proposed_action,          # 必须带 required_gear
            execute=lambda a: actually_do(a),
        )

    动作对象只需暴露 ``required_gear``（int 或 Gear）；
    可用 ``adapters.raw.action()`` 一键包装任意 callable。
    """

    def __init__(
        self,
        utility: UtilityFunction,
        theta: float = 0.0,
        policy: GearPolicy | None = None,
        fallback: FallbackConfig | None = None,
        audit_log: AuditLog | str | None = None,
        initial_gear: Gear = Gear.OBSERVE,
    ):
        self.gate = UtilityGate(utility, theta=theta)
        self.policy = policy or GearPolicy()
        self.fallback_cfg = fallback or FallbackConfig()
        self.audit = audit_log if isinstance(audit_log, AuditLog) else AuditLog(audit_log)
        self.state = RuntimeState(gear=Gear(initial_gear))
        self.audit.record("init", gear=int(self.state.gear), theta=theta)

    # ------------------------------------------------------------------ #

    def step(
        self,
        state: Any,
        action: Any,
        execute: Callable[[Any], Any],
        propose_alternative: AlternativeProposer | None = None,
    ) -> CycleResult:
        """执行一个控制周期（Algorithm 1 的一次迭代）。"""
        if self.state.suspended:
            self.audit.record("suspended_skip", cycle=self.state.cycle)
            return CycleResult(
                executed=False, action=None, gate=None,
                gear_before=self.state.gear, gear_after=self.state.gear,
                suspended=True, error="suspended: awaiting human review",
            )

        gear_before = self.state.gear
        result = self._dispatch(state, action, execute, propose_alternative)

        # 更新 σ / ϵ / clean_streak（Algorithm 1, lines 7/11/13）
        if result.executed and not result.used_fallback:
            self.state.sigma = max(0.0, self.state.sigma - self.policy.sigma_decay)
            self.state.error = False
            self.state.clean_streak += 1
            self.state.consecutive_rejections = 0
        elif result.executed and result.used_fallback:
            self.state.error = False  # σ 保持不变
            self.state.clean_streak += 1
            self.state.consecutive_rejections = 0
        else:
            self.state.sigma += self.policy.sigma_step
            self.state.error = True
            self.state.clean_streak = 0
            self.state.consecutive_rejections += 1

        # 换挡（π_G）
        gear_after = self.policy.next_gear(self.state)
        if gear_after != self.state.gear:
            self.audit.record(
                "gear_transition", cycle=self.state.cycle,
                **{"from": int(self.state.gear), "to": int(gear_after)},
                sigma=round(self.state.sigma, 4),
            )
            self.state.gear = gear_after

        # m 次连续拒绝 → G0 挂起（Theorem 4 的终点）
        if self.state.consecutive_rejections >= self.fallback_cfg.max_consecutive_rejections:
            # FIX-5a：挂起导致的硬降档也要在链上留 gear_transition（换挡不许静默）
            if self.state.gear != Gear.OBSERVE:
                self.audit.record(
                    "gear_transition", cycle=self.state.cycle,
                    **{"from": int(self.state.gear), "to": int(Gear.OBSERVE)},
                    sigma=round(self.state.sigma, 4), reason="suspend",
                )
            self.state.gear = Gear.OBSERVE
            self.state.suspended = True
            result.suspended = True
            self.audit.record("suspend", cycle=self.state.cycle,
                              consecutive_rejections=self.state.consecutive_rejections)

        result.gear_before = gear_before
        result.gear_after = self.state.gear
        self.state.cycle += 1
        return result

    def resume(self) -> None:
        """人工复核后解除挂起（从 G0 重新开始挣档位）。"""
        self.state.suspended = False
        self.state.consecutive_rejections = 0
        self.state.error = False
        self.audit.record("resume", cycle=self.state.cycle)

    # ------------------------------------------------------------------ #

    def _dispatch(
        self,
        state: Any,
        action: Any,
        execute: Callable[[Any], Any],
        propose_alternative: AlternativeProposer | None,
    ) -> CycleResult:
        required = _safe_gear(getattr(action, "required_gear", Gear.EXECUTE))

        # FIX-4：非法 required_gear 视同档位不允许（fail-closed），不抛栈穿透
        if required is None:
            self.audit.record(
                "gate_decision", cycle=self.state.cycle, admitted=False,
                reason=f"invalid required_gear "
                       f"{getattr(action, 'required_gear', None)!r} (attestation rejected)",
            )
            alt = self._try_alternatives(state, action, execute, propose_alternative)
            if alt is not None:
                return alt
            return CycleResult(False, action, None, self.state.gear, self.state.gear)

        # 档位前置闸：超出当前动作空间的动作连门都不进
        if not self.state.gear.permits(required):
            self.audit.record(
                "gate_decision", cycle=self.state.cycle, admitted=False,
                reason=f"gear {self.state.gear.label} does not permit {required.label}",
            )
            alt = self._try_alternatives(state, action, execute, propose_alternative)
            if alt is not None:
                return alt
            return CycleResult(False, action, None, self.state.gear, self.state.gear)

        decision = self.gate.evaluate(state, action)
        self.audit.record(
            "gate_decision", cycle=self.state.cycle, admitted=decision.admitted,
            utility=round(decision.utility, 4), theta=decision.theta, reason=decision.reason,
        )
        # FIX-2：效用异常视同 U=−∞ 拒绝（fail-closed），审计事件与 execute 异常分属
        if decision.meta.get("gate_error"):
            self.audit.record("gate_error", cycle=self.state.cycle,
                              error=decision.meta["gate_error"])
        if decision.admitted:
            return self._run(action, execute, decision, used_fallback=False)

        alt = self._try_alternatives(state, action, execute, propose_alternative)
        if alt is not None:
            return alt
        return CycleResult(False, action, decision, self.state.gear, self.state.gear)

    def _try_alternatives(
        self,
        state: Any,
        rejected: Any,
        execute: Callable[[Any], Any],
        propose_alternative: AlternativeProposer | None,
    ) -> CycleResult | None:
        if propose_alternative is None:
            return None
        for i in range(self.fallback_cfg.max_alternatives):
            # FIX-1：proposer 异常视同无备选——记审计后走正常拒绝分支，
            # 不穿透 step()（对齐 Theorem 4：拒绝路径的 σ/挂起语义照常生效）
            try:
                alt = propose_alternative(state, rejected, i)
            except Exception as exc:
                self.audit.record(
                    "proposer_error", cycle=self.state.cycle, attempt_index=i,
                    error=type(exc).__name__,
                )
                break
            if alt is None:
                break
            required = _safe_gear(getattr(alt, "required_gear", Gear.EXECUTE))
            if required is None:  # FIX-4：非法 gear 视同不允许
                self.audit.record(
                    "gate_decision", cycle=self.state.cycle, admitted=False,
                    reason=f"fallback#{i}: invalid required_gear "
                           f"{getattr(alt, 'required_gear', None)!r} (attestation rejected)",
                )
                continue
            if not self.state.gear.permits(required):
                continue
            decision = self.gate.evaluate(state, alt)
            self.audit.record(
                "gate_decision", cycle=self.state.cycle, admitted=decision.admitted,
                utility=round(decision.utility, 4), theta=decision.theta,
                reason=f"fallback#{i}: {decision.reason}",
            )
            if decision.meta.get("gate_error"):
                self.audit.record("gate_error", cycle=self.state.cycle,
                                  error=decision.meta["gate_error"])
            if decision.admitted:
                return self._run(alt, execute, decision, used_fallback=True)
        return None

    def _run(self, action, execute, decision, used_fallback) -> CycleResult:
        try:
            out = execute(action)
            self.audit.record("execute", cycle=self.state.cycle, fallback=used_fallback)
            return CycleResult(True, action, decision, self.state.gear, self.state.gear,
                               used_fallback=used_fallback, result=out)
        except Exception as exc:  # 执行异常按拒绝处理：σ 上升、ϵ=1
            self.audit.record("execute_error", cycle=self.state.cycle, error=str(exc))
            return CycleResult(False, action, decision, self.state.gear, self.state.gear,
                               used_fallback=used_fallback, error=str(exc))
