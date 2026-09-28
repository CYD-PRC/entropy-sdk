"""v0.1.6 回归钉（KIMICODE-SDKFIX6-20260928）：FIX6-1 record() 返回值隔离。"""
import json

import pytest

from entropy_sdk import EntropyRuntime, Gear, observe


class TestFIX61RecordReturnIsolation:
    """record() 返回值不得是审计真账的内部可变对象。"""

    def test_tamper_returned_entry_memory_mode(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0, initial_gear=Gear.INTEGRATE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        # 涂改返回值顶层字段
        ev = rt.audit.record("probe_top", note="original")
        ev["kind"] = "TAMPERED"
        ev["note"] = "forged"
        kinds = [e["kind"] for e in rt.audit.entries]
        assert "TAMPERED" not in kinds
        assert "probe_top" in kinds
        assert [e for e in rt.audit.entries if e["kind"] == "probe_top"][0]["note"] == "original"

    def test_tamper_nested_container_memory_mode(self):
        rt = EntropyRuntime(utility=lambda s, a: 1.0, initial_gear=Gear.INTEGRATE)
        ev = rt.audit.record("probe_nested", detail={"inner": {"u": 1.5, "tag": "orig"}})
        # 涂改嵌套内层（消毒器为所有容器产出新结构，返回值应与之隔离）
        ev["detail"]["inner"]["tag"] = "forged"
        ev["detail"]["inner"]["extra"] = "injected"
        entries = [e for e in rt.audit.entries if e["kind"] == "probe_nested"]
        assert entries[0]["detail"]["inner"]["tag"] == "orig"
        assert "extra" not in entries[0]["detail"]["inner"]

    def test_file_mode_regression(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: -1.0, theta=0.15,
                            audit_log=str(log), initial_gear=Gear.INTEGRATE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        ev = rt.audit.record("probe_file", detail={"x": 1})
        ev["kind"] = "TAMPERED"
        on_disk = [json.loads(l) for l in open(log, encoding="utf-8")]
        assert "TAMPERED" not in [e["kind"] for e in on_disk]
        assert "probe_file" in [e["kind"] for e in on_disk]
