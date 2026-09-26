"""LangChain 适配：把 Tool 包成"门不过就不执行"的安全工具。

需要 ``pip install entropy-sdk[langchain]``。
"""
from __future__ import annotations

from typing import Any

from ..gear import Gear
from ..runtime import EntropyRuntime


def gated_tool(runtime: EntropyRuntime, tool: Any, required_gear: int | Gear = Gear.EXECUTE,
               state_fn=lambda *a, **k: None):
    """把一个 LangChain Tool 包装成受 EntropyRuntime 门控的工具。

    门拒绝时返回拒绝说明字符串（不执行、不抛异常），
    让 LLM 在下一轮自行调整——拒绝本身是反馈信号。
    """
    def _run(*args: Any, **kwargs: Any) -> str:
        from .raw import action  # 延迟导入，避免硬依赖

        act = action(tool.func if hasattr(tool, "func") else tool,
                     *args, required_gear=required_gear, **kwargs)
        result = runtime.step(state=state_fn(), action=act, execute=lambda a: a())
        if result.executed:
            return str(result.result)
        if result.suspended:
            return "[GATE] runtime suspended after repeated rejections; human review required."
        reason = result.gate.reason if result.gate else "gear does not permit this action"
        return f"[GATE] action rejected: {reason}. Propose a safer alternative."

    from langchain_core.tools import StructuredTool  # noqa: 仅在调用时需要

    return StructuredTool.from_function(
        func=_run,
        name=f"gated_{getattr(tool, 'name', 'tool')}",
        description=(getattr(tool, "description", "") or "")
        + f" [safety-gated, requires gear {Gear(int(required_gear)).label}]",
    )
