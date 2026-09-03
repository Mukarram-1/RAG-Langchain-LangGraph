"""LangGraph assembly and bounded routing."""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents import AgentRegistry
from src.agents.orchestrator import OrchestratorAgent
from src.agents.response_synth import ResponseSynthAgent
from src.agents.result_validator import ResultValidatorAgent
from src.agents.sql_writer import SQLWriterAgent
from src.config import Settings
from src.db.connection import Database
from src.db.schema_loader import SchemaCatalog
from src.executors.sql_executor import SQLExecutor
from src.guardrails.sql_guardrail import SQLGuardrail
from src.models.schemas import DraftStatus, Intent
from src.nodes import (
    decline_request,
    handle_error,
    request_clarification,
    unsupported_route,
)
from src.state import AgentState
from src.validation.result_checks import ResultChecks

MAX_RETRIES = 2


def build_graph(
    model: BaseChatModel,
    catalog: SchemaCatalog,
    database: Database,
    settings: Settings,
) -> Any:
    """Build a compiled graph with an in-memory v1 checkpointer."""
    registry = AgentRegistry()
    registry.register("orchestrator", OrchestratorAgent(model))
    registry.register("sql_writer", SQLWriterAgent(model, catalog))
    registry.register(
        "result_validator",
        ResultValidatorAgent(model, max_retries=MAX_RETRIES),
    )
    registry.register("response_synth", ResponseSynthAgent(model))

    builder = StateGraph(AgentState)
    for name, agent in registry.items():
        builder.add_node(name, agent)

    builder.add_node(
        "sql_guardrail",
        SQLGuardrail(catalog, settings.sql_max_rows),
    )
    builder.add_node("sql_executor", SQLExecutor(database))
    builder.add_node("result_checks", ResultChecks(settings.sql_max_rows))
    builder.add_node("decline", decline_request)
    builder.add_node("unsupported", unsupported_route)
    builder.add_node("clarify", request_clarification)
    builder.add_node("error_handler", handle_error)

    builder.add_edge(START, "orchestrator")
    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "sql_writer": "sql_writer",
            "unsupported": "unsupported",
            "decline": "decline",
            "error_handler": "error_handler",
        },
    )
    builder.add_conditional_edges(
        "sql_writer",
        route_after_sql_writer,
        {
            "sql_guardrail": "sql_guardrail",
            "clarify": "clarify",
            "error_handler": "error_handler",
        },
    )
    builder.add_conditional_edges(
        "sql_guardrail",
        route_after_guardrail,
        {
            "sql_executor": "sql_executor",
            "sql_writer": "sql_writer",
            "error_handler": "error_handler",
        },
    )
    builder.add_conditional_edges(
        "sql_executor",
        route_after_executor,
        {
            "result_checks": "result_checks",
            "error_handler": "error_handler",
        },
    )
    builder.add_edge("result_checks", "result_validator")
    builder.add_conditional_edges(
        "result_validator",
        route_after_validator,
        {
            "sql_writer": "sql_writer",
            "response_synth": "response_synth",
            "error_handler": "error_handler",
        },
    )
    builder.add_edge("response_synth", END)
    builder.add_edge("decline", END)
    builder.add_edge("unsupported", END)
    builder.add_edge("clarify", END)
    builder.add_edge("error_handler", END)

    return builder.compile(checkpointer=InMemorySaver())


def route_after_orchestrator(state: AgentState) -> str:
    if state.get("error"):
        return "error_handler"
    intent = state.get("intent", Intent.OUT_OF_SCOPE)
    if intent == Intent.STRUCTURED_LOOKUP:
        return "sql_writer"
    if intent == Intent.RAG_SEARCH:
        return "unsupported"
    return "decline"


def route_after_sql_writer(state: AgentState) -> str:
    if state.get("error"):
        return "error_handler"
    if state.get("draft_status") == DraftStatus.NEEDS_CLARIFICATION.value:
        return "clarify"
    return "sql_guardrail"


def route_after_guardrail(state: AgentState) -> str:
    if state.get("sql_valid"):
        return "sql_executor"
    if state.get("retry_count", 0) <= MAX_RETRIES:
        return "sql_writer"
    return "error_handler"


def route_after_executor(state: AgentState) -> str:
    return "error_handler" if state.get("error") else "result_checks"


def route_after_validator(state: AgentState) -> str:
    if state.get("error"):
        return "error_handler"
    if state.get("retry_requested"):
        return "sql_writer"
    return "response_synth"
