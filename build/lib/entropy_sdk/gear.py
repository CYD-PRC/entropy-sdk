"""
Gear 状态系统（论文 Definition 1）

五级执行档位，动作空间单调嵌套：A0 ⊂ A1 ⊂ A2 ⊂ A3 ⊂ A4 = A。
档位的语义是"动作空间的上限"，不是速度——降级收缩的是 agent 能做什么，
不是做得多慢。
"""
from __future__ import annotations

from enum import IntEnum


class Gear(IntEnum):
    OBSERVE = 0    # G0: 只读观察 / 安全保持，无副作用
    SUGGEST = 1    # G1: 生成候选计划，无外部副作用
    PLAN = 2       # G2: 有界、可逆或保全性恢复动作
    EXECUTE = 3    # G3: 可独立选择有副作用的动作
    INTEGRATE = 4  # G4: 系统级协调（多智能体下为涌现属性，见论文 §6.3）

    @property
    def label(self) -> str:
        return _LABELS[self]

    def permits(self, required: "Gear") -> bool:
        """嵌套动作空间：当前档位 g 允许所有 required_gear <= g 的动作。"""
        return Gear(required) <= self


_LABELS = {
    Gear.OBSERVE: "Observe",
    Gear.SUGGEST: "Suggest",
    Gear.PLAN: "Plan",
    Gear.EXECUTE: "Execute",
    Gear.INTEGRATE: "Integrate",
}
