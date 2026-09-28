"""v0.1.9 终局回归钉（KIMICODE-SDKFIX9-20260928）。

FIX9-1 的断言端一律严格解析钩子（parse_constant 抛异常——不设钩子是假绿）。
"""
import json

import pytest

STRICT = lambda s: json.loads(
    s, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"nonfinite leaked: {x}")))

from entropy_sdk import EntropyRuntime, observe


def _disk_entries(log):
    return [STRICT(l) for l in open(log, encoding="utf-8")]


class TestFIX91NonfiniteFloatKeys:
    """非有限 float 键 → 字符串标记（与 value 侧同记号），严格 JSON 可消费。"""

    @pytest.mark.parametrize("k,marker", [
        (float("nan"), "nan"), (float("inf"), "+inf"), (float("-inf"), "-inf"),
    ])
    def test_nonfinite_key_becomes_marker(self, tmp_path, k, marker):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={k: "value"})
        e = _disk_entries(log)[-1]["detail"]
        assert e[marker] == "value"

    def test_finite_float_key_preserved(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={1.5: "v"})
        e = _disk_entries(log)[-1]["detail"]
        assert e["1.5"] == "v"  # json.dumps 对有限 float 键的自有语义

    def test_inf_key_collides_with_marker_string_key(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={"+inf": "first", float("inf"): "second"})
        e = _disk_entries(log)[-1]["detail"]
        # inf 键降级后与既有 "+inf" 串键同键形 → 走既有撞键路径，保留先见者
        assert e["+inf"] == "first"
        assert e["_audit_meta"]["key_collision"] is True


class TestFIX92AuditMetaNamespace:
    """审计元数据收进 _audit_meta；用户字段零丢失。"""

    def test_user_key_collision_field_not_lost(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={"_key_collision": "user-value", 1: "a", "1": "b"})
        e = _disk_entries(log)[-1]["detail"]
        assert e["_key_collision"] == "user-value"          # 用户原值不丢
        assert e["_audit_meta"]["key_collision"] is True    # 审计标记在场且隔离

    def test_user_audit_meta_field_shadowed_kept(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={"_audit_meta": "user-meta", 1: "a", "1": "b"})
        e = _disk_entries(log)[-1]["detail"]
        assert e["_audit_meta"]["user_field_shadowed"] == "user-meta"
        assert e["_audit_meta"]["key_collision"] is True

    def test_no_collision_no_meta(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: 1.0, audit_log=str(log))
        rt.audit.record("probe", detail={"a": 1})
        e = _disk_entries(log)[-1]["detail"]
        assert "_audit_meta" not in e
