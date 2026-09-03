"""Small deterministic terminal graph nodes."""

from typing import Any

from langchain_core.messages import AIMessage

from src.state import AgentState


def decline_request(state: AgentState) -> dict[str, Any]:
    return _finalize(
        "This request is outside the supported read-only legal data lookup "
        "scope."
    )


def unsupported_route(state: AgentState) -> dict[str, Any]:
    return _finalize(
        "This question requires semantic document search. That agent is not "
        "implemented in the current structured-lookup milestone."
    )


def request_clarification(state: AgentState) -> dict[str, Any]:
    question = state.get("clarification", "").strip()
    if not question:
        question = (
            "Please provide the company, domain, case, invoice, or other "
            "identifier needed for this lookup."
        )
    return _finalize(question)


def handle_error(state: AgentState) -> dict[str, Any]:
    return _finalize(
        "I could not complete that lookup safely. Please rephrase it with a "
        "specific company, domain, case, invoice, or date."
    )


def _finalize(answer: str) -> dict[str, Any]:
    return {
        "final_response": answer,
        "messages": [AIMessage(content=answer)],
    }
