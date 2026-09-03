"""Bounded conversation context for follow-up questions."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.state import AgentState


def recent_turns(
    state: AgentState,
    max_messages: int = 6,
    max_chars: int = 800,
) -> list[BaseMessage]:
    """Return prior human/assistant turns without re-adding the current input."""
    question = state.get("question", "").strip()
    messages = [
        message
        for message in state.get("messages", [])
        if isinstance(message, (HumanMessage, AIMessage))
    ]
    if (
        messages
        and isinstance(messages[-1], HumanMessage)
        and _content_text(messages[-1]).strip() == question
    ):
        messages = messages[:-1]

    bounded: list[BaseMessage] = []
    for message in messages[-max_messages:]:
        content = _truncate(_content_text(message), max_chars)
        message_type = HumanMessage if isinstance(message, HumanMessage) else AIMessage
        bounded.append(message_type(content=content))
    return bounded


def _content_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return str(content)


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return f"{value[: max(0, max_chars - 15)]}...[truncated]"
