"""零框架适配：把任意 Python callable 包装成被门控的动作。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..gear import Gear


@dataclass
class RawAction:
    """最小动作包装。"""

    fn: Callable[..., Any]
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    required_gear: int | Gear = Gear.EXECUTE
    description: str = ""

    def __call__(self) -> Any:
        return self.fn(*self.args, **self.kwargs)


def action(
    fn: Callable[..., Any],
    *args: Any,
    required_gear: int | Gear = Gear.EXECUTE,
    description: str = "",
    **kwargs: Any,
) -> RawAction:
    """一行包装：``action(send_email, to, body, required_gear=Gear.EXECUTE)``。"""
    return RawAction(fn=fn, args=args, kwargs=kwargs,
                     required_gear=required_gear, description=description)


def observe(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> RawAction:
    """只读动作快捷包装：required_gear=G0，任何档位可执行。"""
    return action(fn, *args, required_gear=Gear.OBSERVE, **kwargs)
