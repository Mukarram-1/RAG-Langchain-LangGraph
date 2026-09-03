"""Agent registry for composable graph assembly."""

from collections.abc import Iterator

from src.agents.base import AgentNode


class AgentRegistry:
    """Register graph nodes without coupling their implementations."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentNode] = {}

    def register(self, name: str, agent: AgentNode) -> None:
        if not name or name in self._agents:
            raise ValueError(f"Agent name must be unique: {name!r}")
        self._agents[name] = agent

    def items(self) -> Iterator[tuple[str, AgentNode]]:
        yield from self._agents.items()

    def __contains__(self, name: str) -> bool:
        return name in self._agents


__all__ = ["AgentRegistry"]
