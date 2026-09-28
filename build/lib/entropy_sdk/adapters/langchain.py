"""LangChain 适配：把 Tool 包成"门不过就不执行"的安全工具。

需要 ``pip install entropy-sdk[langchain]``。
"""
from __future__ import annotations

from typing import Any

from ..gear import Gear
from ..runtime import EntropyRuntime, _safe_gear


def gated_tool(runtime: EntropyRuntime, tool: Any, required_gear: int | Gear = Gear.EXECUTE,
               state_fn=lambda *a, **k: None):
    """把一个 LangChain Tool 包装成受 EntropyRuntime 门控的工具。

    门拒绝时返回拒绝说明字符串（不执行、不抛异常），
    让 LLM 在下一轮自行调整——拒绝本身是反馈信号。
    """
    # FIX5-2：与 runtime 同一严格度——构造期即拒非法 gear（3.0/"3"/True 等），
    # 消灭「adapter 静默截断、runtime 拒绝」的两处判定不一致
    gear = _safe_gear(required_gear)
    if gear is None:
        raise ValueError(f"invalid required_gear {required_gear!r} "
                         "(want Gear instance or plain int 0-4)")

    def _run(*args: Any, **kwargs: Any) -> str:
        from .raw import action  # 延迟导入，避免硬依赖

        # FIX-7：description 透传，效用函数可按工具身份定价
        act = action(tool.func if hasattr(tool, "func") else tool,
                     *args, required_gear=gear,
                     description=getattr(tool, "description", "") or getattr(tool, "name", ""),
                     **kwargs)
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
        + f" [safety-gated, requires gear {gear.label}]",
        # FIX-6：透传原工具的 args_schema——不带它，带参工具没有正常调用路径
        args_schema=getattr(tool, "args_schema", None),
    )
