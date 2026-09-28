# entropy-sdk

**An embeddable, gear-based safety control layer for autonomous agents** — the
SDK distillation of the EntropyRuntime paper's core abstractions
([arXiv:2607.00334](https://arxiv.org/abs/2607.00334)).

> Make an AI's degree of autonomy observable, governable, and accountable.

[![test](https://github.com/CYD-PRC/entropy-sdk/actions/workflows/test.yml/badge.svg)](https://github.com/CYD-PRC/entropy-sdk/actions/workflows/test.yml)
![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-%3E%3D3.10-blue)

> Test readings are reported from **raw CI logs, not badge conclusions**:
> latest verified reading — **119 passed / 0 skipped** across Python 3.10–3.13
> (Actions run inspected line-by-line). The packaging-smoke job's
> **96 passed / 3 skipped** is the intended bare-wheel form (the 3 skips are the
> named langchain-extra cases in a no-`langchain_core` environment) — the two
> numbers measure different install surfaces, they are not a discrepancy.
> A green badge alone is not evidence.

Unlike [CYD-PRC/entropyruntime](https://github.com/CYD-PRC/entropyruntime)
(the full production system — FastAPI + PostgreSQL + Redis + OPA), this
repository is the **zero-dependency, embeddable** minimal control layer:
`pip install` and five lines of code wire it into any agent loop.

## Core abstractions

| Abstraction | Paper | SDK |
|---|---|---|
| Five-level gear ladder G0–G4 | Definition 1 (𝒜₀⊂…⊂𝒜₄) | `Gear` |
| Utility gate U(s,a) ≥ θ | Definitions 2–3, Theorem 2 | `UtilityGate` |
| Slow-up-fast-down state machine | §4 Gear state machine | `GearPolicy` |
| Event-driven fallback | Theorem 4 | `FallbackConfig` |
| Runtime state ρ=(g,σ,ϵ) | Definition 4 | `RuntimeState` |
| Audit chain | §5/§8 empirical requirements | `AuditLog` (append-only JSONL) |

## Design rules

1. **Pure stdlib core, zero dependencies.** Framework adapters (LangChain /
   PydanticAI) ship as optional extras.
2. **fail-closed.** The utility function must be injected explicitly; there is
   no fail-open switch — the utility gate is the sole dispatch channel
   (Theorem 2, enforced in code).
3. **Audit chain built in.** Every gate decision, gear transition, and
   suspension is appended to JSONL. `gate_acceptance_rate()` and
   `gear_histogram()` produce the empirical data that the paper's Theorem 1
   assumption and Theorem 3 prediction call for.

## Quickstart

```bash
pip install entropy-sdk
```

```python
from entropy_sdk import EntropyRuntime, Gear, action, observe

# 1. Inject your domain utility function (the SDK ships no built-in U)
def my_utility(state, act):
    return state.task_gain(act) + 2.0 * state.safety(act) - 0.5 * act.cost

# Note: action()'s **kwargs are call parameters of the wrapped function,
# not utility metadata. Feed metadata to the utility via post-creation
# assignment (act.utility_value = ... style).
# 2. Create the runtime (theta is the only safety-vs-output knob)
runtime = EntropyRuntime(utility=my_utility, theta=0.15,
                         audit_log="audit.jsonl")

# 3. Every agent action goes through the gate
result = runtime.step(
    state=my_state,
    action=action(delete_records, "users", required_gear=Gear.EXECUTE),
    execute=lambda a: a(),
    propose_alternative=my_fallback_planner,  # optional: rejected-action fallback
)

if result.suspended:
    alert_human()          # m consecutive rejections -> suspend at G0, await review
    runtime.resume()       # after human review, gears must be re-earned
```

### Gear semantics

| Gear | Name | Permitted actions |
|---|---|---|
| G0 | Observe | Read-only observation, safe holding |
| G1 | Suggest | Side-effect-free candidate plans |
| G2 | Plan | Bounded, reversible recovery actions |
| G3 | Execute | Independently chosen side-effecting actions |
| G4 | Integrate | System-level coordination (an emergent property of all-G3 fleets) |

**Slow up, fast down** (earned autonomy): escalation requires σ < σ_low **and**
h consecutive clean cycles — every gear must be re-earned (v0.1.2+);
de-escalation on σ overflow or error is immediate. Autonomy is earned, and it
can always be revoked.

A runnable version of this narrative lives in
[`examples/lifecycle_demo.py`](examples/lifecycle_demo.py)
(`python examples/lifecycle_demo.py`).

## Framework adapters

```python
# LangChain: pip install entropy-sdk[langchain]
from entropy_sdk.adapters.langchain import gated_tool
safe_tool = gated_tool(runtime, my_tool, required_gear=Gear.EXECUTE)

# PydanticAI-compatible callable decorator: pip install entropy-sdk[pydanticai]
from entropy_sdk.adapters.pydanticai import gated

@gated(runtime, required_gear=Gear.EXECUTE)
def delete_records(table: str) -> str: ...
```

On rejection the adapters **return an explanatory string instead of raising** —
rejection itself is feedback the agent can act on next turn.

(Note on naming: this is a **PydanticAI-compatible callable decorator**, not a
true PydanticAI adapter — it is a pure stdlib decorator with zero framework
dependencies (the `pydanticai` extra list is intentionally empty, FIX-8) and has
**not been validated against a real PydanticAI runtime**. Just
`from entropy_sdk.adapters.pydanticai import gated`.)

(LangChain boundary: `args_schema` passthrough only works for real
StructuredTool instances carrying a schema; bare tool objects (func only, no
args_schema) remain limited by the wrapper's `*args/**kwargs` signature.)

## Threat model boundaries (paper armor — read before deploying)

1. **The gate is the sole dispatch channel — only inside execution paths the
   SDK controls.** A caller holding the raw callable can bypass the gate
   (`tool.func(...)` skips it); the SDK governs calls that go through
   `runtime.step`, not references in the caller's hands.
2. **`required_gear` is a caller-side attestation contract.** The SDK trusts
   the label's truthfulness; whether labels may be trusted (who is allowed to
   tag an action's gear) is the deployer's responsibility — the SDK
   fail-closes on *invalid* values, but is not responsible for
   under-tagged powerful actions.
3. **The gate governs invocation, not transactions.** Side effects that
   already happened inside `execute` are not rolled back — the semantics are
   invocation control, not atomicity. Implement compensation in your own
   `execute` if you need transactional behavior.
4. **`resume()` does not clear σ** (design semantics, not a bug): human
   review ≠ instant restoration of trust — σ persists after resuming, and
   gears must be re-earned through clean cycles.
5. **`except Exception` does not cover `BaseException`**: if a
   proposer/execute callback raises SystemExit/KeyboardInterrupt, the state
   machine can still desynchronize — this is standard Python practice;
   callers must not raise BaseException inside callbacks.
6. **Concurrency**: the runtime is lock-free. Under current CPython (GIL),
   8000/8000 cycles measured with no lost updates; on free-threaded Python
   (3.13t+), the read-modify-write of cycle/σ can lose updates — serialize
   externally when using multiple threads.
7. **A deleted audit file reads as empty** (fail-open read path): in file
   mode, `entries`/metrics return empty results for a missing chain file
   rather than raising — asymmetric with the fail-closed write path. Deployers
   should monitor the audit file's existence (a missing append-only chain file
   is itself an event).

## Empirical data API

```python
runtime.audit.gate_acceptance_rate()  # gate acceptance rate (Theorem 1, p1≥p3)
runtime.audit.gear_histogram()        # gear transition histogram (Theorem 3)
```

Every run produces data for the framework's empirical validation — a unique
value of the SDK relative to the full system.

Contract: audit fields should be JSON-compatible; unknown object types are
recorded as their `str()` form (uniform across memory and file modes).

## Changelog & security record

- [CHANGELOG.md](CHANGELOG.md) — versioned changes, including behavior-change
  and compatibility notes.
- 中文文档：[README.zh-CN.md](README.zh-CN.md)

## License

MIT © Wang Miaosheng (ORCID: 0009-0003-2767-2421) — see [LICENSE](LICENSE).
