"""v0.1.5 回归钉（KIMICODE-SDKFIX5-20260927）。

FIX5-1 的断言端一律用严格解析钩子（json.loads 默认接受 NaN/Infinity——
不设钩子的测试是假绿，本票拒收假绿）。
"""
import json

import pytest

STRICT_LOADS = lambda s: json.loads(
    s, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"nonfinite leaked: {x}")))

from entropy_sdk import EntropyRuntime, Gear, observe


def _strict_entries(log_path):
    return [STRICT_LOADS(l) for l in open(log_path, encoding="utf-8")]


class TestFIX51NestedSanitize:
    """嵌套容器内的非有限 float 必须被消毒（字符串标记），且不炸循环/深递归。"""

    def _run_with_meta(self, tmp_path, meta):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: -1.0, theta=0.15,
                            audit_log=str(log), initial_gear=Gear.INTEGRATE)
        rt.audit.record("probe", detail=meta)
        return _strict_entries(log)  # 严格解析：裸 NaN/Infinity 在此即炸

    def test_nested_dict(self, tmp_path):
        entries = self._run_with_meta(tmp_path, {"a": {"u": float("nan")}})
        assert entries[-1]["detail"]["a"]["u"] == "nan"

    def test_nested_list(self, tmp_path):
        entries = self._run_with_meta(tmp_path, {"a": [float("inf")]})
        assert entries[-1]["detail"]["a"][0] == "+inf"

    def test_nested_tuple(self, tmp_path):
        entries = self._run_with_meta(tmp_path, {"a": (float("-inf"), 1)})
        assert entries[-1]["detail"]["a"][0] == "-inf"
        assert entries[-1]["detail"]["a"][1] == 1

    def test_three_layer_mixed(self, tmp_path):
        meta = {"x": [{"y": {"z": float("nan")}}, (float("inf"),)]}
        entries = self._run_with_meta(tmp_path, meta)
        d = entries[-1]["detail"]["x"]
        assert d[0]["y"]["z"] == "nan"
        assert d[1][0] == "+inf"

    def test_cycle_does_not_crash(self, tmp_path):
        d = {}
        d["self"] = d  # 循环引用
        entries = self._run_with_meta(tmp_path, d)
        assert "truncated" in str(entries[-1]["detail"]["self"])

    def test_depth_cap_marks_truncation(self, tmp_path):
        d = cur = {}
        for _ in range(40):
            cur["down"] = {}
            cur = cur["down"]
        cur["u"] = float("nan")
        entries = self._run_with_meta(tmp_path, d)  # 不炸栈
        text = json.dumps(entries[-1]["detail"])
        assert "truncated" in text

    def test_top_level_format_unchanged(self, tmp_path):
        # 顶层既有行为不动：null + <key>_nonfinite 侧键（v0.1.2 记号）
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: float("nan"), theta=0.15,
                            audit_log=str(log), initial_gear=Gear.INTEGRATE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        gd = [e for e in _strict_entries(log) if e["kind"] == "gate_decision"][-1]
        assert gd["utility"] is None and gd["utility_nonfinite"] == "nan"

    def test_passthrough_types_untouched(self, tmp_path):
        meta = {"s": "text", "i": 3, "b": True, "n": None, "f": 1.5, "l": [1, "x"]}
        entries = self._run_with_meta(tmp_path, meta)
        assert entries[-1]["detail"] == meta


class TestFIX52AdapterGearContract:
    """langchain adapter 构造期与 runtime 同一严格度（_safe_gear）。"""

    @pytest.mark.parametrize("bad", [3.0, "3", True, False, 3.9])
    def test_invalid_gear_rejected_at_construction(self, bad):
        from entropy_sdk.adapters.langchain import gated_tool
        rt = EntropyRuntime(utility=lambda s, a: 1.0)
        tool = type("T", (), {"func": lambda: 1, "name": "noop",
                              "description": ""})()
        with pytest.raises(ValueError):
            gated_tool(rt, tool, required_gear=bad)

    def test_valid_int_and_gear_accepted(self):
        # int(3.9) == 3 是真 int（构造期已截断完成），接受——语义同 runtime
        from entropy_sdk.adapters.langchain import gated_tool
        rt = EntropyRuntime(utility=lambda s, a: 1.0)
        tool = type("T", (), {"func": lambda: 1, "name": "noop",
                              "description": ""})()
        g = gated_tool(rt, tool, required_gear=int(3.9))  # = 3 → EXECUTE
        assert g is not None
        g2 = gated_tool(rt, tool, required_gear=Gear.PLAN)
        assert g2 is not None
