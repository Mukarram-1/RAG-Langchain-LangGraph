"""Conversation-window tests."""

from langchain_core.messages import AIMessage, HumanMessage

from src.conversation import recent_turns


def test_recent_turns_excludes_current_question_and_truncates() -> None:
    state = {
        "question": "What is its demand status?",
        "messages": [
            HumanMessage(content="Find Scooter's Coffee"),
            AIMessage(content="x" * 100),
            HumanMessage(content="What is its demand status?"),
        ],
    }

    turns = recent_turns(state, max_messages=6, max_chars=30)

    assert len(turns) == 2
    assert turns[0].content == "Find Scooter's Coffee"
    assert turns[1].content.endswith("...[truncated]")
    assert all(
        message.content != "What is its demand status?"
        for message in turns
    )


def test_recent_turns_keeps_only_latest_bounded_messages() -> None:
    state = {
        "question": "current",
        "messages": [
            HumanMessage(content="old"),
            AIMessage(content="old answer"),
            HumanMessage(content="recent"),
            AIMessage(content="recent answer"),
            HumanMessage(content="current"),
        ],
    }

    turns = recent_turns(state, max_messages=2)

    assert [message.content for message in turns] == [
        "recent",
        "recent answer",
    ]
