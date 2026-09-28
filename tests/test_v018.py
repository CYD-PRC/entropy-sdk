"""v0.1.8 收官回归钉（KIMICODE-SDKFIX8-20260928）：FIX8-1 键侧降级 + FIX8-2 bool 统一拒。"""
import json

import pytest

from entropy_sdk import EntropyRuntime, FallbackConfig, Gear, GearPolicy, observe


class TestFIX81KeySideDegradation:
    """dict 键侧与值侧同规则降级；合法 JSON 键类型保留；撞键留标记。"""

    class K:
        def __str__(self):
            return "<K>"

    def test_object_key_becomes_str(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0)
        rt.audit.record("probe", detail={self.K(): "value"})
        e = [x for x in rt.audit.entries if x["kind"] == "probe"][0]
        assert e["detail"] == {"<K>": "value"}

    def test_nested_object_key(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={"outer": {self.K(): 1}})
        on_disk = [json.loads(l) for l in open(log, encoding="utf-8")]
        assert on_disk[-1]["detail"]["outer"] == {"<K>": 1}

    def test_legal_json_keys_preserved(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0)
        rt.audit.record("probe", detail={"s": 1, 1: 2, 1.5: 3, True: 4, None: 5})
        e = [x for x in rt.audit.entries if x["kind"] == "probe"][0]["detail"]
        assert set(e.keys()) == {"s", 1, 1.5, True, None}

    def test_collision_keeps_first_and_marks(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0)
        rt.audit.record("probe", detail={1: "a", "1": "b"})  # JSON 序列化后同键
        e = [x for x in rt.audit.entries if x["kind"] == "probe"][0]["detail"]
        assert e["_key_collision"] is True
        # 保留先见者：int 键 1 的值 "a" 不被 "b" 静默覆盖
        assert e[1] == "a" or e["1"] == "a"

    def test_file_mode_collision_marker_on_disk(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={1: "a", "1": "b"})
        on_disk = [json.loads(l) for l in open(log, encoding="utf-8")]
        assert on_disk[-1]["detail"]["_key_collision"] is True


class TestFIX82BoolRejectedEverywhere:
    """同一 SDK 同一 bool 态度：数值配置 bool 一律 ValueError。"""

    def test_theta_bool(self):
        with pytest.raises(ValueError):
            EntropyRuntime(utility=lambda s, a: 1.0, theta=True)

    @pytest.mark.parametrize("field", ["sigma_low", "sigma_high", "sigma_decay", "sigma_step"])
    def test_policy_numeric_bool(self, field):
        with pytest.raises(ValueError):
            GearPolicy(**{field: True})
        with pytest.raises(ValueError):
            GearPolicy(**{field: False})

    def test_fallback_bool(self):
        # FallbackConfig 两字段自 v0.1.2 起已拒 bool（回归保持）
        with pytest.raises(ValueError):
            FallbackConfig(max_alternatives=True)
        with pytest.raises(ValueError):
            FallbackConfig(max_consecutive_rejections=False)

    def test_patience_bool(self):
        # patience 自 FIX2-2 起已拒 bool（回归保持）
        with pytest.raises(ValueError):
            GearPolicy(patience=True)

    def test_legal_values_ok(self):
        EntropyRuntime(utility=lambda s, a: 1.0, theta=0.0)
        GearPolicy(sigma_low=0, sigma_high=1, sigma_decay=0.0, sigma_step=1.0, patience=1)
        FallbackConfig(max_alternatives=0, max_consecutive_rejections=1)
