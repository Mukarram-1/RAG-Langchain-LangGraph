"""Shared agent contracts."""

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from src.state import AgentState

StateUpdate = dict[str, Any]
NodeCallable = Callable[[AgentState], Awaitable[StateUpdate]]


class AgentNode(Protocol):
    """Protocol implemented by every async graph agent."""

    async def __call__(self, state: AgentState) -> StateUpdate:
        ...
