"""适配器基座：一个动作协议 + 一个提案协议，接任何 agent 框架。"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..gear import Gear


@runtime_checkable
class GatedAction(Protocol):
    """被门控的动作必须声明自己需要的最低档位。

    这是嵌套动作空间 A0⊂…⊂A4 的实现侧契约：
    required_gear=G0 的动作（只读）在任何档位都允许；
    required_gear=G3 的动作（有副作用）只在 Execute 以上放行。
    """

    required_gear: int | Gear


class AgentAdapter(Protocol):
    """Agent 框架适配协议（对齐生产仓 interfaces/agent_adapter.py 的轻量版）。"""

    def propose(self, state: Any, gear: Gear, history: list[dict]) -> GatedAction:
        """按当前档位生成候选动作。实现侧应遵守档位语义：
        档位越低，生成的动作越保守。"""
        ...

    def execute(self, action: GatedAction) -> Any:
        """真正执行。只会在门放行后被调用。"""
        ...
