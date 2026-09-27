"""v0.1.4 回归：FIX4-1 非有限效用门内校验（Grok 首发的 fail-open 方向）。"""
import json

import pytest

from entropy_sdk import EntropyRuntime, Gear, observe


class TestFIX41NonfiniteUtility:
    """NaN / +inf / -inf 一律拒绝——同一把尺两个方向都闭上。"""

    @pytest.mark.parametrize("bad_u,marker", [
        (float("nan"), "nan"),
        (float("inf"), "+inf"),
        (float("-inf"), "-inf"),
    ])
    def test_nonfinite_rejected_with_signed_marker(self, tmp_path, bad_u, marker):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: bad_u, theta=0.15,
                            audit_log=str(log), initial_gear=Gear.INTEGRATE)
        ran = []
        r = rt.step(state=None, action=observe(lambda: ran.append(1)),
                    execute=lambda a: a())
        assert not r.executed and ran == []
        assert "nonfinite utility" in r.gate.reason
        line = [json.loads(l) for l in open(log, encoding="utf-8")
                if '"gate_decision"' in l][-1]
        assert line["utility"] is None
        assert line["utility_nonfinite"] == marker  # FIX2-6 符号标记

    def test_plus_inf_was_fail_open_before(self):
        # +inf >= θ 恒真——FIX4-1 前会放行执行；现在必须拒绝且不产生副作用
        rt = EntropyRuntime(utility=lambda s, a: float("inf"), theta=0.15,
                            initial_gear=Gear.INTEGRATE)
        ran = []
        r = rt.step(state=None, action=observe(lambda: ran.append(1)),
                    execute=lambda a: a())
        assert not r.executed and ran == []
        assert rt.state.sigma > 0  # 走拒绝路径

    def test_finite_behavior_unchanged(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0, theta=0.15,
                            initial_gear=Gear.INTEGRATE)
        r = rt.step(state=None, action=observe(lambda: 42), execute=lambda a: a())
        assert r.executed and r.result == 42
