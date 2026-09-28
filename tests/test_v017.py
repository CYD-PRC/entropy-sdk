"""v0.1.7 回归钉（KIMICODE-SDKFIX7-20260928）：FIX7-1~3。"""
import json

import pytest

from entropy_sdk import EntropyRuntime, FallbackConfig, Gear, action, observe


class TestFIX71EntriesNestedIsolation:
    """entries() 嵌套容器必须与真账/缓存隔离（深拷贝）。"""

    def test_memory_mode_nested_tamper(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0, initial_gear=Gear.INTEGRATE)
        rt.audit.record("probe", detail={"nested": {"x": "orig"}})
        ev = rt.audit.entries
        ev[-1]["detail"]["nested"]["x"] = "tampered"
        truth = [e for e in rt.audit.entries if e["kind"] == "probe"][0]
        assert truth["detail"]["nested"]["x"] == "orig"

    def test_file_mode_cache_not_poisoned(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, theta=0.15,
                            audit_log=str(log), initial_gear=Gear.INTEGRATE)
        rt.audit.record("probe", detail={"nested": {"x": "orig"}})
        # 触发缓存建立（entries 读一遍）
        _ = rt.audit.entries
        # 经 entries 返回值涂改嵌套内层 → 缓存真值不变、磁盘不变
        ev = rt.audit.entries
        ev[-1]["detail"]["nested"]["x"] = "tampered"
        again = [e for e in rt.audit.entries if e["kind"] == "probe"][0]
        assert again["detail"]["nested"]["x"] == "orig"
        on_disk = [json.loads(l) for l in open(log, encoding="utf-8")]
        assert on_disk[-1]["detail"]["nested"]["x"] == "orig"


class TestFIX72IntegerFloatNormalization:
    """FallbackConfig(3.0)：构造接受后 runtime 必须真能跑完 fallback loop。"""

    def test_int_float_runs_full_fallback_loop(self):
        rt = EntropyRuntime(
            utility=lambda s, a: getattr(a, "utility_value", 1.0), theta=0.15,
            fallback=FallbackConfig(max_alternatives=3.0),
            initial_gear=Gear.INTEGRATE)
        bad = observe(lambda: None)
        bad.utility_value = -1.0

        def alt(state, rejected, i):
            a = observe(lambda: f"alt{i}")
            a.utility_value = 1.0
            return a

        r = rt.step(state=None, action=bad, execute=lambda a: a(),
                    propose_alternative=alt)
        # 主动作被拒 → 进入 fallback loop（range 不炸）→ 备选执行成功
        assert r.executed and r.used_fallback
        assert r.result == "alt0"

    def test_fractional_still_rejected(self):
        with pytest.raises(ValueError):
            FallbackConfig(max_alternatives=1.5)

    def test_normalized_field_is_int(self):
        cfg = FallbackConfig(max_alternatives=3.0, max_consecutive_rejections=5.0)
        assert type(cfg.max_alternatives) is int
        assert type(cfg.max_consecutive_rejections) is int


class TestFIX73UnknownObjectDegrade:
    """未知类型对象统一 str() 降级（与 file mode default=str 对齐）。"""

    class NoCopy:
        def __deepcopy__(self, memo):
            raise RuntimeError("no copy")

        def __str__(self):
            return "<NoCopy instance>"

    def test_memory_mode_no_crash_str_form(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0)
        ev = rt.audit.record("probe", detail={"obj": self.NoCopy()})
        assert ev["detail"]["obj"] == "<NoCopy instance>"
        assert rt.audit.entries[-1]["detail"]["obj"] == "<NoCopy instance>"

    def test_file_mode_same_semantics(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={"obj": self.NoCopy()})
        on_disk = [json.loads(l) for l in open(log, encoding="utf-8")]
        assert on_disk[-1]["detail"]["obj"] == "<NoCopy instance>"
