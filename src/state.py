"""Lean shared state for the LangGraph workflow."""

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    """Only values needed by downstream nodes are checkpointed."""

    messages: Annotated[list[AnyMessage], add_messages]
    question: str
    intent: str
    intent_reason: str
    draft_status: str
    clarification: str
    generated_sql: str
    sql_rationale: str
    sql_valid: bool
    sql_error: str
    guardrail_feedback: str
    retry_count: int
    referenced_tables: list[str]
    query_results: list[dict[str, Any]]
    row_count: int
    checks_note: str
    result_empty: bool
    result_truncated: bool
    all_values_null: bool
    validation_verdict: str
    validation_reason: str
    retry_advice: str
    retry_requested: bool
    final_response: str
    error: str
