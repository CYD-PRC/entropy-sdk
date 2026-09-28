"""
entropy-sdk — EntropyRuntime 控制层的可嵌入 SDK

论文同款核心抽象（arXiv:2607.00334）：
Gear 五级档位 · Utility Gate 效用门 · 事件驱动 Fallback · append-only 审计链。

设计铁律：
1. 核心纯 stdlib，零依赖；
2. fail-closed —— 效用函数必须显式注入，门是唯一调度通道；
3. 每次判定自动落审计链，为经验验证生产数据。
"""
from .adapters.raw import RawAction, action, observe
from .fallback import FallbackConfig
from .gate import GateDecision, UtilityGate
from .gear import Gear
from .policy import GearPolicy
from .runtime import CycleResult, EntropyRuntime
from .state import AuditLog, RuntimeState

__version__ = "0.1.9"
__all__ = [
    "Gear", "UtilityGate", "GateDecision", "GearPolicy", "FallbackConfig",
    "RuntimeState", "AuditLog", "EntropyRuntime", "CycleResult",
    "RawAction", "action", "observe",
]
