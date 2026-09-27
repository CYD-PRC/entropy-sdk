"""v0.1.2 契约硬化回归：FIX2-1~6 逐条钉死（KIMICODE-SDKFIX2-20260927）。"""
import json

import pytest

from entropy_sdk import EntropyRuntime, FallbackConfig, Gear, GearPolicy, action, observe
from entropy_sdk.runtime import _safe_gear


class TestFIX21StrictGearAttestation:
    """只收 Gear 实例与真 int；bool/float/str/None/object/越界/±inf 全拒。"""

    @pytest.mark.parametrize("bad", [
        3.9, 3.7, "3", "EXECUTE", True, False, 5, -1,
        float("inf"), float("-inf"), None, object(),
    ])
    def test_rejected_forms(self, bad):
        assert _safe_gear(bad) is None

    @pytest.mark.parametrize("good", list(Gear) + [0, 1, 2, 3, 4])
    def test_accepted_forms(self, good):
        assert _safe_gear(good) == Gear(int(good))

    def test_bool_true_does_not_become_suggest(self):
        # 洞的原形：Gear(True) 因 IntEnum 值查找 True==1 静默成 SUGGEST
        assert _safe_gear(True) is None
        assert _safe_gear(False) is None

    def test_step_with_bool_gear_no_crash(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0, initial_gear=Gear.INTEGRATE)
        ran = []
        bad = action(lambda: ran.append(1), required_gear=True)
        r = rt.step(state=None, action=bad, execute=lambda a: a())
        assert not r.executed and ran == []


class TestFIX22FiniteAndInteger:
    def test_theta_nan_inf_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError):
                EntropyRuntime(utility=lambda s, a: 1.0, theta=bad)

    def test_patience_nan_and_fractional_rejected(self):
        with pytest.raises(ValueError):
            GearPolicy(patience=float("nan"))
        with pytest.raises(ValueError):
            GearPolicy(patience=1.5)
        with pytest.raises(ValueError):
            GearPolicy(patience=True)
        GearPolicy(patience=2.0)  # 整数值 float 合法

    def test_sigma_nan_rejected(self):
        with pytest.raises(ValueError):
            GearPolicy(sigma_decay=float("nan"))
        with pytest.raises(ValueError):
            GearPolicy(sigma_low=float("inf"))

    def test_fallback_noninteger_rejected(self):
        with pytest.raises(ValueError):
            FallbackConfig(max_alternatives=1.5)
        with pytest.raises(ValueError):
            FallbackConfig(max_consecutive_rejections=float("nan"))


class TestFIX23MaxAlternativesSemantics:
    def test_zero_disables_fallback_proposer_never_called(self):
        calls = []

        def proposer(state, rejected, i):
            calls.append(i)
            return None

        rt = EntropyRuntime(utility=lambda s, a: -1.0, theta=0.15,
                            fallback=FallbackConfig(max_alternatives=0),
                            initial_gear=Gear.EXECUTE)
        r = rt.step(state=None, action=action(lambda: None), execute=lambda a: a(),
                    propose_alternative=proposer)
        assert not r.executed
        assert calls == []                      # 零调用
        assert rt.state.sigma > 0               # 直接进拒绝流程

    def test_upper_bound(self):
        with pytest.raises(ValueError):
            FallbackConfig(max_alternatives=101)
        with pytest.raises(ValueError):
            FallbackConfig(max_alternatives=10**9)
        FallbackConfig(max_alternatives=100)    # 上界本身合法
        FallbackConfig(max_alternatives=0)      # 0 合法（关闭 fallback）


class TestFIX24CleanStreakResetOnUpgrade:
    """每档都挣满 h 个干净周期：G0→G4 全升程 = 4h 个周期（h=3 ⇒ 12）。"""

    def test_exact_trajectory(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0, theta=0.15,
                            initial_gear=Gear.OBSERVE)
        good = observe(lambda: 1)
        traj = []
        for _ in range(13):
            rt.step(state=None, action=good, execute=lambda a: a())
            traj.append(int(rt.state.gear))
        # c3→G1, c6→G2, c9→G3, c12→G4（每档 3 个干净周期）
        assert traj == [0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4]

    def test_no_ladder_after_first_patience(self):
        # v0.1.1 旧形态是 [0,0,1,2,3,4,…]——钉死不再出现
        rt = EntropyRuntime(utility=lambda s, a: 1.0, theta=0.15,
                            initial_gear=Gear.OBSERVE)
        good = observe(lambda: 1)
        for _ in range(4):
            rt.step(state=None, action=good, execute=lambda a: a())
        assert rt.state.gear == Gear.SUGGEST  # 第 4 周期不再连升

    def test_demote_and_suspend_paths_streak_zero(self):
        """判词：降档/挂起路径无需额外清零——拒绝分支已先把 clean_streak 清零。"""
        rt = EntropyRuntime(utility=lambda s, a: -1.0, theta=0.15,
                            fallback=FallbackConfig(max_consecutive_rejections=2),
                            initial_gear=Gear.EXECUTE)
        bad = observe(lambda: None)
        rt.step(state=None, action=bad, execute=lambda a: a())
        assert rt.state.clean_streak == 0       # 降档路径
        rt.step(state=None, action=bad, execute=lambda a: a())
        assert rt.state.suspended and rt.state.clean_streak == 0  # 挂起路径


class TestFIX25ReadCache:
    def test_external_append_visible_and_cached(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, theta=0.15,
                            audit_log=str(log), initial_gear=Gear.OBSERVE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        n1 = len(rt.audit.entries)
        # 外部追加（另一写入方）：mtime+size 变化 ⇒ 缓存失效可见
        with open(log, "a", encoding="utf-8") as f:
            f.write('{"kind": "external"}\n')
        entries = rt.audit.entries
        assert len(entries) == n1 + 1
        assert entries[-1]["kind"] == "external"
        # 再读一次走缓存（同 key）：corrupt_lines 语义不漂移
        assert rt.audit.corrupt_lines == 0

    def test_memory_mode_corrupt_lines_zero(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        assert rt.audit.corrupt_lines == 0
        assert len(rt.audit.entries) >= 2


class TestFIX26SignedNonfiniteMarker:
    def test_markers_carry_sign(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        # gate_error 路径产生 utility=-inf
        rt = EntropyRuntime(utility=lambda s, a: 1 / 0, theta=0.15,
                            audit_log=str(log), initial_gear=Gear.INTEGRATE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        lines = [json.loads(l) for l in open(log, encoding="utf-8")]
        gd = [e for e in lines if e["kind"] == "gate_decision"][-1]
        assert gd["utility"] is None and gd["utility_nonfinite"] == "-inf"
