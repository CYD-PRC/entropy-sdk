"""v0.1.1 硬化回归：每个 FIX 一条钉死用例 + 真副作用夹具（TEST-1/2）。"""
import json

import pytest

from entropy_sdk import EntropyRuntime, FallbackConfig, Gear, GearPolicy, action, observe


def make_runtime(**kw):
    return EntropyRuntime(utility=lambda s, a: getattr(a, "utility_value", 1.0),
                          theta=0.15, **kw)


class TestFIX1ProposerError:
    """proposer 异常 → proposer_error 落账 + 视同无备选（不穿透 step）。"""

    def test_proposer_blows_up_m_times_suspends(self):
        rt = make_runtime(fallback=FallbackConfig(max_consecutive_rejections=3),
                          initial_gear=Gear.EXECUTE)

        def boom(state, rejected, i):
            raise RuntimeError("planner down")

        bad = action(lambda: None, required_gear=Gear.PLAN)
        bad.utility_value = -1.0
        for _ in range(3):
            r = rt.step(state=None, action=bad, execute=lambda a: a(),
                        propose_alternative=boom)
        assert rt.state.suspended and rt.state.gear == Gear.OBSERVE
        errs = [e for e in rt.audit.entries if e["kind"] == "proposer_error"]
        assert errs and all(e["error"] == "RuntimeError" for e in errs)
        assert errs[0]["attempt_index"] == 0


class TestFIX2UtilityError:
    """utility 异常 → gate_error + 视同 U=−∞ 拒绝；与 execute 异常分属。"""

    def test_utility_exception_is_fail_closed(self):
        rt = EntropyRuntime(utility=lambda s, a: 1 / 0, theta=0.15,
                            initial_gear=Gear.INTEGRATE)
        ran = []
        r = rt.step(state=None, action=observe(lambda: ran.append(1)),
                    execute=lambda a: a())
        assert not r.executed and ran == []          # 拒绝而非炸穿
        assert r.gate is not None and r.gate.utility == float("-inf")
        assert "gate_error" in r.gate.reason
        assert rt.state.sigma > 0                     # σ 按拒绝路径上升
        kinds = [e["kind"] for e in rt.audit.entries]
        assert "gate_error" in kinds

    def test_gate_error_distinct_from_execute_error(self):
        rt = make_runtime(initial_gear=Gear.INTEGRATE)
        bad_exec = observe(lambda: 1 / 0)
        r = rt.step(state=None, action=bad_exec, execute=lambda a: a())
        kinds = [e["kind"] for e in rt.audit.entries]
        assert "execute_error" in kinds and "gate_error" not in kinds
        assert r.error is not None


class TestFIX3ConfigValidation:
    def test_policy_rejects_bad(self):
        with pytest.raises(ValueError):
            GearPolicy(patience=0)
        with pytest.raises(ValueError):
            GearPolicy(sigma_low=2.0, sigma_high=1.0)
        with pytest.raises(ValueError):
            GearPolicy(sigma_decay=-0.1)
        with pytest.raises(ValueError):
            GearPolicy(sigma_step=-1)

    def test_fallback_rejects_bad(self):
        # FIX2-3（v0.1.2）：max_alternatives=0 恢复合法（关闭 fallback），
        # 非法面 = 负数 / 超上界 100 / 非整数
        with pytest.raises(ValueError):
            FallbackConfig(max_alternatives=-1)
        with pytest.raises(ValueError):
            FallbackConfig(max_alternatives=101)
        with pytest.raises(ValueError):
            FallbackConfig(max_consecutive_rejections=0)
        FallbackConfig(max_alternatives=0)  # 合法：关闭 fallback


class TestFIX4InvalidGear:
    """非法 required_gear → 档位前置闸拒绝路径，不抛 ValueError 穿透。"""

    def test_invalid_gear_rejected_not_raised(self):
        rt = make_runtime(initial_gear=Gear.INTEGRATE)
        ran = []
        bad = action(lambda: ran.append(1), required_gear=5)
        r = rt.step(state=None, action=bad, execute=lambda a: a())
        assert not r.executed and ran == []
        assert r.gate is None
        # 拒绝后 σ 升、ϵ=1 会触发降档——最后一条是 gear_transition；
        # 钉的是拒绝路径上的 gate_decision 理由
        gd = [e for e in rt.audit.entries
              if e["kind"] == "gate_decision" and "invalid required_gear" in e.get("reason", "")]
        assert gd

    def test_invalid_gear_on_alternative(self):
        rt = make_runtime(initial_gear=Gear.INTEGRATE)
        bad = action(lambda: None, required_gear=Gear.EXECUTE)
        bad.utility_value = -1.0
        weird = action(lambda: None, required_gear=99)
        r = rt.step(state=None, action=bad, execute=lambda a: a(),
                    propose_alternative=lambda s, rej, i: weird)
        assert not r.executed  # 非法备选被拒，流程完好
        assert any("invalid required_gear" in e.get("reason", "")
                   for e in rt.audit.entries)


class TestFIX5AuditChain:
    def test_suspend_records_gear_transition(self):
        rt = make_runtime(fallback=FallbackConfig(max_consecutive_rejections=2),
                          initial_gear=Gear.EXECUTE)
        bad = action(lambda: None, required_gear=Gear.PLAN)
        bad.utility_value = -1.0
        rt.step(state=None, action=bad, execute=lambda a: a())
        rt.step(state=None, action=bad, execute=lambda a: a())
        kinds = [e["kind"] for e in rt.audit.entries]
        assert "suspend" in kinds
        trans = [e for e in rt.audit.entries
                 if e["kind"] == "gear_transition" and e.get("reason") == "suspend"]
        # 每次拒绝都先经 π_G 降档（3→2→1），挂起时的硬降是 G1→G0
        assert trans and trans[0]["to"] == 0 and trans[0]["from"] == 1
        assert kinds.index("gear_transition") < kinds.index("suspend")

    def test_file_backed_entries_read_from_disk(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = make_runtime(audit_log=str(log), initial_gear=Gear.OBSERVE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        entries = rt.audit.entries  # 文件模式不再恒空
        assert any(e["kind"] == "gate_decision" for e in entries)

    def test_corrupt_lines_skipped_and_counted(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = make_runtime(audit_log=str(log), initial_gear=Gear.OBSERVE)
        rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        with open(log, "a", encoding="utf-8") as f:
            f.write('{"kind": "broken", "ts": \n')   # 坏行（半截写入形态）
        entries = rt.audit.entries
        assert rt.audit.corrupt_lines == 1
        assert all(isinstance(e, dict) for e in entries)

    def test_nonfinite_sanitized_and_nan_fails_closed(self, tmp_path):
        log = tmp_path / "audit.jsonl"
        rt = EntropyRuntime(utility=lambda s, a: float("nan"), theta=0.15,
                            audit_log=str(log), initial_gear=Gear.INTEGRATE)
        r = rt.step(state=None, action=observe(lambda: 1), execute=lambda a: a())
        assert not r.executed                      # NaN 效用 fail-closed（不变）
        line = [l for l in open(log, encoding="utf-8")
                if '"gate_decision"' in l][-1]
        json.loads(line)                           # 严格解析器合法
        e = json.loads(line)
        assert e["utility"] is None and e["utility_nonfinite"] == "nan"  # FIX2-6：标记带符号


class TestResumeKeepsSigma:
    """DOC-2 钉死：resume() 不清 σ（人工复核 ≠ 信任瞬时恢复）。"""

    def test_resume_preserves_sigma(self):
        rt = make_runtime(fallback=FallbackConfig(max_consecutive_rejections=2),
                          initial_gear=Gear.EXECUTE)
        bad = action(lambda: None, required_gear=Gear.PLAN)
        bad.utility_value = -1.0
        rt.step(state=None, action=bad, execute=lambda a: a())
        rt.step(state=None, action=bad, execute=lambda a: a())
        sigma_at_suspend = rt.state.sigma
        assert rt.state.suspended
        rt.resume()
        assert rt.state.sigma == sigma_at_suspend > 0
        assert not rt.state.suspended


class TestTEST1RealSideEffects:
    """真副作用夹具：G3 动作仅在 gear>=G3 时执行，G2 及以下零副作用。"""

    def test_execute_gear_real_mutation(self):
        world = {"deleted": []}

        def delete_records(table):
            world["deleted"].append(table)
            return f"deleted {table}"

        rt = make_runtime(initial_gear=Gear.OBSERVE)
        # FIX2-4 后：每档都要挣满 h=3——G0→G1 在 c3，G1→G2 在 c6
        good = observe(lambda: 1)
        for _ in range(6):
            rt.step(state=None, action=good, execute=lambda a: a())
        assert rt.state.gear == Gear.PLAN
        # G2 试 G3 动作：零副作用（且这次拒绝会立即降到 G1——ϵ=1 语义）
        r = rt.step(state=None, action=action(delete_records, "users",
                                              required_gear=Gear.EXECUTE),
                    execute=lambda a: a())
        assert not r.executed and world["deleted"] == []
        assert rt.state.gear == Gear.SUGGEST
        # 重新挣到 G3：G1→G2 三个周期 + G2→G3 三个周期（每档重新挣）
        for _ in range(6):
            rt.step(state=None, action=good, execute=lambda a: a())
        assert rt.state.gear == Gear.EXECUTE
        r = rt.step(state=None, action=action(delete_records, "users",
                                              required_gear=Gear.EXECUTE),
                    execute=lambda a: a())
        assert r.executed and world["deleted"] == ["users"]


class TestFIX6LangChainSchema:
    """带参工具的 args_schema 透传（langchain-core 不在环境则跳过）。"""

    def test_args_schema_passthrough(self):
        pytest.importorskip("langchain_core")
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel

        class Args(BaseModel):
            table: str

        def delete_records(table: str) -> str:
            return f"deleted {table}"

        tool = StructuredTool.from_function(
            func=delete_records, name="delete_records", args_schema=Args,
            description="delete rows")
        from entropy_sdk.adapters.langchain import gated_tool
        rt = make_runtime(initial_gear=Gear.INTEGRATE)
        gated = gated_tool(rt, tool, required_gear=Gear.EXECUTE)
        assert gated.args_schema is Args
        assert "deleted users" in gated.invoke({"table": "users"})


class TestFIX7DescriptionPassthrough:
    def test_pydanticai_description_reaches_utility(self):
        from entropy_sdk.adapters.pydanticai import gated
        seen = []

        def pricing_utility(state, act):
            seen.append(act.description)
            return 1.0

        rt = EntropyRuntime(utility=pricing_utility, theta=0.15,
                            initial_gear=Gear.INTEGRATE)

        @gated(rt, required_gear=Gear.EXECUTE)
        def delete_records(table: str) -> str:
            """删表"""
            return f"deleted {table}"

        assert delete_records("users") == "deleted users"
        assert seen == ["删表"]

    def test_langchain_description_passthrough(self):
        pytest.importorskip("langchain_core")
        from entropy_sdk.adapters.langchain import gated_tool
        seen = []
        rt = EntropyRuntime(utility=lambda s, a: (seen.append(a.description), 1.0)[1],
                            theta=0.15, initial_gear=Gear.INTEGRATE)
        tool = type("T", (), {"func": lambda: 1, "name": "noop",
                              "description": "空转工具"})()
        gated_tool(rt, tool).invoke({})
        assert seen == ["空转工具"]
