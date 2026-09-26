# entropy-sdk

**可嵌入的 Agent 档位安全控制层** —— EntropyRuntime 论文（[arXiv:2607.00334](https://arxiv.org/abs/2607.00334)）核心抽象的 SDK 化提炼。

> 让 AI 的自主程度看得见、管得住、说得清。

与 [CYD-PRC/entropyruntime](https://github.com/CYD-PRC/entropyruntime)（生产级完整系统，FastAPI + PostgreSQL + Redis + OPA）不同，本仓库是**零依赖、可嵌入**的最小控制层：`pip install` 之后 5 行代码接进任何 agent 循环。

## 核心抽象

| 抽象 | 论文对应 | SDK |
|---|---|---|
| 五级档位 G0–G4 | Definition 1（𝒜₀⊂…⊂𝒜₄） | `Gear` |
| 效用门 U(s,a) ≥ θ | Definitions 2–3, Theorem 2 | `UtilityGate` |
| 慢升快降状态机 | §4 Gear state machine | `GearPolicy` |
| 事件驱动 fallback | Theorem 4 | `FallbackConfig` |
| 运行时状态 ρ=(g,σ,ϵ) | Definition 4 | `RuntimeState` |
| 审计链 | §5/§8 实证需求 | `AuditLog`（append-only JSONL） |

## 设计铁律

1. **核心纯 stdlib，零依赖**。框架适配（LangChain / PydanticAI）走 extras，按需安装。
2. **fail-closed**。效用函数必须显式注入，没有 fail-open 开关——门是唯一调度通道（Theorem 2 在代码层的贯彻）。
3. **审计链内置**。每次门判定、换挡、挂起自动落 JSONL；`gate_acceptance_rate()` 和 `gear_histogram()` 直接产出论文 Theorem 1 假设与 Theorem 3 预测所需的经验数据。

## 快速开始

```bash
# 尚未发布 PyPI —— 请源码安装（v0.1.1 起）
pip install -e .
```

```python
from entropy_sdk import EntropyRuntime, Gear, action, observe

# 1. 注入你的领域效用函数（SDK 不内置 U）
def my_utility(state, act):
    return state.task_gain(act) + 2.0 * state.safety(act) - 0.5 * act.cost

# 注意：action() 的 **kwargs 是被包装函数的调用参数，不是效用元数据；
# 要给效用函数喂元数据，用创建后赋值（act.utility_value = ... 形态）。
# 2. 创建运行时（θ 是唯一的安全-产能旋钮）
runtime = EntropyRuntime(utility=my_utility, theta=0.15,
                         audit_log="audit.jsonl")

# 3. 每个 agent 动作都过门
result = runtime.step(
    state=my_state,
    action=action(delete_records, "users", required_gear=Gear.EXECUTE),
    execute=lambda a: a(),
    propose_alternative=my_fallback_planner,  # 可选：拒绝后的备选生成器
)

if result.suspended:
    alert_human()          # m 次连续拒绝 → G0 挂起，等待复核
    runtime.resume()       # 人工复核后从 G0 重新挣档位
```

### 档位语义

| 档位 | 名称 | 允许的动作 |
|---|---|---|
| G0 | Observe | 只读观察、安全保持 |
| G1 | Suggest | 生成无副作用的候选计划 |
| G2 | Plan | 有界、可逆的恢复性动作 |
| G3 | Execute | 独立选择有副作用的动作 |
| G4 | Integrate | 系统级协调（多智能体下为全员 G3 的涌现属性） |

**慢升快降**：升档需要 σ < σ_low 且连续 h 个干净周期；σ 越界或出错立即降一档。自主度是挣出来的，且随时可撤回。

## 框架适配

```python
# LangChain：pip install entropy-sdk[langchain]
from entropy_sdk.adapters.langchain import gated_tool
safe_tool = gated_tool(runtime, my_tool, required_gear=Gear.EXECUTE)

# PydanticAI：pip install entropy-sdk[pydanticai]
from entropy_sdk.adapters.pydanticai import gated

@gated(runtime, required_gear=Gear.EXECUTE)
def delete_records(table: str) -> str: ...
```

门拒绝时**返回说明字符串而非抛异常**——拒绝本身是反馈信号，agent 下一轮可自行调整。

（PydanticAI extra 说明：该适配器是**纯 stdlib 装饰器**，实际零框架依赖——
`pip install entropy-sdk[pydanticai]` 的 extra 列表为空（FIX-8 名实对齐），直接
`from entropy_sdk.adapters.pydanticai import gated` 即可用。）

## 威胁模型边界（论文护甲，部署前必读）

1. **门是唯一调度通道——仅在 SDK 控制的执行路径内成立**。使用者拿到 callable
   后可以直接调用绕过（`tool.func(...)` 不过门）；SDK 管的是「经过 runtime.step
   的调用」，管不了使用者自己手里的引用。
2. **`required_gear` 是调用方声明契约（attestation）**。SDK 信任标签的真实性；
   标签是否可信（谁有权给动作标档位）是部署方的责任——SDK 只对非法值 fail-closed，
   不对「低标高档动作」负责。
3. **门管调用不管事务**。`execute` 内已经发生的副作用不回滚——门的语义是
   invocation 控制，不是 atomicity。需要事务性请在你的 execute 里自己实现补偿。
4. **`resume()` 不清 σ**（设计语义，非缺陷）：人工复核 ≠ 信任瞬时恢复——
   挂起解除后 σ 保留，档位要在干净周期里重新挣下来。
5. **并发**：runtime 无锁。当前 CPython（GIL）下实测 8000/8000 周期无丢失更新；
   free-threaded Python（3.13t+）下 cycle/σ 的读-改-写存在丢失更新风险——
   多线程使用请外部串行化。

## 实证数据接口

```python
runtime.audit.gate_acceptance_rate()  # 门接受率（Theorem 1 假设 p1≥p3 的观测口径）
runtime.audit.gear_histogram()        # gear 转移直方图（Theorem 3 最终镇定的证据）
```

每一次运行都在为框架的经验验证生产数据——这是 SDK 相对完整系统的独特价值。

## 许可证

MIT © Wang Miaosheng (ORCID: 0009-0003-2767-2421)
