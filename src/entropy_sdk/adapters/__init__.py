"""Agent 框架适配器。raw 零依赖；langchain/pydanticai 按需 extras 安装。"""
from .base import AgentAdapter, GatedAction
from .raw import RawAction, action, observe

__all__ = ["AgentAdapter", "GatedAction", "RawAction", "action", "observe"]
