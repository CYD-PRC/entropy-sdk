"""v0.1.3 终审尾款回归：FIX3-1~6 逐条钉死（KIMICODE-SDKFIX3-20260927）。"""
import json

import pytest

from entropy_sdk import EntropyRuntime, FallbackConfig, Gear, GearPolicy, action, observe


def make(**kw):
    return EntropyRuntime(utility=lambda s, a: getattr(a, "utility_value", 1.0),
                          theta=0.15, **kw)


class TestFIX31EntriesIsolation:
    """涂改 entries 返回值 ⇒ metrics 与磁盘双双不失真。"""

    def test_mutation_does_not_leak(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = make(audit_log=str(log), initial_gear=Gear.INTEGRATE)
        good = observe(lambda: 1)
        bad = observe(lambda: 1)
        bad.utility_value = -1.0
        rt.step(state=None, action=good, execute=lambda a: a())
        rt.step(state=None, action=bad, execute=lambda a: a())
        assert rt.audit.gate_acceptance_rate() == 0.5

        # 涂改对外返回的条目
        for e in rt.audit.entries:
            if e.get("kind") == "gate_decision":
                e["admitted"] = True
        # metrics 与磁盘双双不失真
        assert rt.audit.gate_acceptance_rate() == 0.5
        on_disk = [json.loads(l) for l in open(log, encoding="utf-8")]
        gd = [e for e in on_disk if e["kind"] == "gate_decision"]
        assert [e["admitted"] for e in gd] == [True, False]

    def test_memory_mode_isolated_too(self):
        rt = make(initial_gear=Gear.INTEGRATE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        for e in rt.audit.entries:
            e["kind"] = "TAMPERED"
        assert any(e["kind"] == "gate_decision" for e in rt.audit.entries)


class TestFIX32DemoteClearsStreak:
    """σ 降档路径（成功执行但 σ 超阈）也清零 clean_streak。"""

    def test_sigma_demote_clears_streak(self):
        # 窄 σ 带 + decay=0：拒绝后 σ 停在超阈区，下一周期成功执行仍被降档
        policy = GearPolicy(sigma_low=0.05, sigma_high=0.15, sigma_decay=0.0,
                            sigma_step=0.2, patience=3)
        rt = EntropyRuntime(utility=lambda s, a: getattr(a, "utility_value", 1.0),
                            theta=0.15, policy=policy, initial_gear=Gear.EXECUTE)
        bad = observe(lambda: 1)
        bad.utility_value = -1.0
        rt.step(state=None, action=bad, execute=lambda a: a())   # 拒绝：σ=0.2，降 G3→G2
        assert rt.state.gear == Gear.PLAN
        # 成功执行但 σ=0.2 仍超阈 ⇒ 再降 G2→G1；本周期是「成功执行」，
        # clean_streak 刚 +1——FIX3-2 前会残留 1，修复后必须为 0
        r = rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        assert r.executed
        assert rt.state.gear == Gear.SUGGEST
        assert rt.state.clean_streak == 0


class TestFIX34StrictInitialGear:
    @pytest.mark.parametrize("bad", [3.0, "3", True, False, 5, None, object()])
    def test_invalid_initial_gear_raises(self, bad):
        with pytest.raises(ValueError):
            EntropyRuntime(utility=lambda s, a: 1.0, initial_gear=bad)

    @pytest.mark.parametrize("good", [3, Gear.EXECUTE, Gear.OBSERVE, 0])
    def test_valid_initial_gear_ok(self, good):
        rt = EntropyRuntime(utility=lambda s, a: 1.0, initial_gear=good)
        assert rt.state.gear == Gear(int(good))


class TestFIX36DocClaims:
    """文档声明与实现一致（审计文件删除的 fail-open 读路径）。"""

    def test_deleted_audit_file_reads_empty(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = make(audit_log=str(log), initial_gear=Gear.INTEGRATE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        assert len(rt.audit.entries) >= 2
        log.unlink()
        # 声明的形态：静默返回空（fail-open 读路径），不抛
        assert rt.audit.entries == []
        assert rt.audit.gate_acceptance_rate() is None
