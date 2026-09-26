"""PydanticAI 适配：工具函数装饰器，门控逻辑与框架解耦。

需要 ``pip install entropy-sdk[pydanticai]``。
"""
from __future__ import annotations

import functools
from typing import Any, Callable

from ..gear import Gear
from ..runtime import EntropyRuntime


def gated(runtime: EntropyRuntime, required_gear: int | Gear = Gear.EXECUTE,
          state_fn=lambda *a, **k: None):
    """装饰任意工具函数，使其经过 EntropyRuntime 效用门。

    拒绝时返回说明字符串而非抛异常，让 agent 把拒绝当作反馈。
    用法::

        @gated(runtime, required_gear=Gear.EXECUTE)
        def delete_records(table: str) -> str: ...
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            from .raw import action

            act = action(fn, *args, required_gear=required_gear, **kwargs)
            result = runtime.step(state=state_fn(), action=act, execute=lambda a: a())
            if result.executed:
                return result.result
            if result.suspended:
                return "[GATE] runtime suspended; human review required."
            reason = result.gate.reason if result.gate else "gear does not permit this action"
            return f"[GATE] rejected: {reason}"

        return wrapper

    return decorator
