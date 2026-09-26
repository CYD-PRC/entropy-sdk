"""核心行为测试：对应论文 Theorem 2 / 3 / 4 的可执行断言。"""
import pytest

from entropy_sdk import EntropyRuntime, FallbackConfig, Gear, GearPolicy, action, observe


def risky_utility(state, act):
    return getattr(act, "utility_value", 1.0)


def make_runtime(**kw):
    return EntropyRuntime(utility=risky_utility, theta=0.15, **kw)


class TestExecutionSafety:
    """Theorem 2：被执行的动作必有 U >= θ；门是唯一调度通道。"""

    def test_negative_utility_never_executed(self):
        rt = make_runtime(initial_gear=Gear.INTEGRATE)
        ran = []
        bad = action(lambda: ran.append(1), required_gear=Gear.EXECUTE)
        bad.utility_value = -1.0
        r = rt.step(state=None, action=bad, execute=lambda a: a())
        assert not r.executed and ran == []

    def test_no_fail_open(self):
        with pytest.raises(ValueError):
            EntropyRuntime(utility=None)

    def test_fallback_also_gated(self):
        rt = make_runtime(initial_gear=Gear.INTEGRATE)
        ran = []
        bad = action(lambda: ran.append("primary"), required_gear=Gear.EXECUTE)
        bad.utility_value = -1.0

        def worse_alt(state, rejected, i):
            a = action(lambda: ran.append(f"alt{i}"), required_gear=Gear.EXECUTE)
            a.utility_value = -0.5
            return a

        r = rt.step(state=None, action=bad, execute=lambda a: a(),
                    propose_alternative=worse_alt)
        assert not r.executed and ran == []


class TestGearPermission:
    """嵌套动作空间：低档位不放行高档位动作，连门都不进。"""

    def test_low_gear_blocks_side_effect(self):
        rt = make_runtime(initial_gear=Gear.OBSERVE)
        ran = []
        act = action(lambda: ran.append(1), required_gear=Gear.EXECUTE)
        r = rt.step(state=None, action=act, execute=lambda a: a())
        assert not r.executed and ran == []
        assert r.gate is None  # 档位前置闸拦截，未进入效用评估

    def test_observe_action_allowed_anywhere(self):
        rt = make_runtime(initial_gear=Gear.OBSERVE)
        r = rt.step(state=None, action=observe(lambda: 42), execute=lambda a: a())
        assert r.executed and r.result == 42


class TestGearDynamics:
    """慢升快降 + 最终镇定（Theorem 1/3 的行为级对应）。"""

    def test_slow_escalation_needs_patience(self):
        policy = GearPolicy(patience=3)
        rt = make_runtime(policy=policy, initial_gear=Gear.OBSERVE)
        good = observe(lambda: 1)
        for _ in range(2):  # 只攒 2 个干净周期，不够 h=3
            rt.step(state=None, action=good, execute=lambda a: a())
        assert rt.state.gear == Gear.OBSERVE
        rt.step(state=None, action=good, execute=lambda a: a())
        assert rt.state.gear == Gear.SUGGEST  # 第 3 个干净周期后升档

    def test_immediate_deescalation_on_error(self):
        rt = make_runtime(initial_gear=Gear.EXECUTE)
        bad = action(lambda: None, required_gear=Gear.EXECUTE)
        bad.utility_value = -1.0
        rt.step(state=None, action=bad, execute=lambda a: a())
        assert rt.state.gear == Gear.PLAN  # 立即降一档

    def test_eventual_stabilization(self):
        rt = make_runtime(initial_gear=Gear.OBSERVE)
        good = observe(lambda: 1)
        for _ in range(60):
            rt.step(state=None, action=good, execute=lambda a: a())
        assert rt.state.gear == Gear.INTEGRATE  # 良性环境下收敛到 G4


class TestFallbackCompleteness:
    """Theorem 4：m 次连续拒绝后到达 G0 挂起，且可经人工复核恢复。"""

    def test_suspend_after_m_rejections_then_resume(self):
        rt = make_runtime(fallback=FallbackConfig(max_consecutive_rejections=3),
                          initial_gear=Gear.EXECUTE)
        bad = action(lambda: None, required_gear=Gear.PLAN)
        bad.utility_value = -1.0
        for _ in range(3):
            rt.step(state=None, action=bad, execute=lambda a: a())
        assert rt.state.suspended and rt.state.gear == Gear.OBSERVE

        # 挂起期间一切动作被拒
        r = rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        assert not r.executed and r.suspended

        rt.resume()
        r = rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        assert r.executed


class TestAudit:
    """审计链：门判定与换挡全留痕，直方图/接受率可算。"""

    def test_audit_trail_and_metrics(self):
        rt = make_runtime(initial_gear=Gear.OBSERVE)
        good = observe(lambda: 1)
        bad = observe(lambda: 1)
        bad.utility_value = -1.0
        rt.step(state=None, action=good, execute=lambda a: a())
        rt.step(state=None, action=bad, execute=lambda a: a())

        kinds = [e["kind"] for e in rt.audit.entries]
        assert "init" in kinds and kinds.count("gate_decision") == 2
        assert rt.audit.gate_acceptance_rate() == 0.5
