"""End-to-end graph wiring test with deterministic fakes."""

import logging
from typing import Any

import pytest
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableLambda

from src.config import Settings
from src.db.schema_loader import ColumnSchema, SchemaCatalog, TableSchema
from src.graph import build_graph
from src.models.schemas import (
    DraftStatus,
    GroundingVerdict,
    Intent,
    RouteDecision,
    SQLDraft,
    SynthesizedAnswer,
    ValidationDecision,
)
from src.nodes import handle_error


class FakeModel:
    def with_structured_output(self, schema: type[Any]) -> RunnableLambda:
        async def respond(_: Any) -> Any:
            if schema is RouteDecision:
                return RouteDecision(
                    intent=Intent.STRUCTURED_LOOKUP,
                    reason="Exact record lookup.",
                )
            if schema is SQLDraft:
                return SQLDraft(
                    sql='SELECT "id" FROM "public"."Domain"',
                    rationale="Fetch the requested identifier.",
                )
            if schema is ValidationDecision:
                return ValidationDecision(
                    verdict=GroundingVerdict.OK,
                    reason="The row answers the question.",
                )
            return SynthesizedAnswer(
                answer="The confirmed domain is domain-1. Source: Domain."
            )

        return RunnableLambda(respond)


class FakeDatabase:
    async def fetch(self, query: str, *args: Any) -> list[dict[str, str]]:
        assert "LIMIT 100" in query
        return [{"id": "domain-1"}]


@pytest.mark.asyncio
async def test_structured_lookup_graph_path(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    table = TableSchema(
        schema="public",
        name="Domain",
        columns={"id": ColumnSchema("id", "uuid", False)},
    )
    catalog = SchemaCatalog(tables={table.qualified_name: table})
    settings = Settings(_env_file=None)
    graph = build_graph(
        FakeModel(),  # type: ignore[arg-type]
        catalog,
        FakeDatabase(),  # type: ignore[arg-type]
        settings,
    )

    output = await graph.ainvoke(
        {
            "question": "Find domain one",
            "messages": [HumanMessage(content="Find domain one")],
            "error": "",
            "sql_error": "",
        },
        config={"configurable": {"thread_id": "test-thread"}},
    )

    assert output["intent"] == Intent.STRUCTURED_LOOKUP.value
    assert isinstance(output["intent"], str)
    assert output["sql_valid"] is True
    assert output["row_count"] == 1
    assert "domain-1" in output["final_response"]
    assert "```json" not in output["final_response"]
    assert "[orchestrator]" in caplog.text
    assert "[sql_writer]" in caplog.text
    assert "[sql_guardrail]" in caplog.text
    assert "[sql_executor]" in caplog.text

    await graph.ainvoke(
        {
            "question": "Find domain one again",
            "messages": [HumanMessage(content="Find domain one again")],
            "error": "",
            "sql_error": "",
        },
        config={"configurable": {"thread_id": "test-thread"}},
    )
    assert "Deserializing unregistered type" not in caplog.text


class ClarificationModel(FakeModel):
    def with_structured_output(self, schema: type[Any]) -> RunnableLambda:
        if schema is not SQLDraft:
            return super().with_structured_output(schema)

        async def clarify(_: Any) -> SQLDraft:
            return SQLDraft(
                status=DraftStatus.NEEDS_CLARIFICATION,
                rationale="A company identifier is required.",
                clarification="Which company do you mean?",
            )

        return RunnableLambda(clarify)


@pytest.mark.asyncio
async def test_clarification_does_not_execute_sql() -> None:
    table = TableSchema(
        schema="public",
        name="Domain",
        columns={"id": ColumnSchema("id", "uuid", False)},
    )
    graph = build_graph(
        ClarificationModel(),  # type: ignore[arg-type]
        SchemaCatalog(tables={table.qualified_name: table}),
        FakeDatabase(),  # type: ignore[arg-type]
        Settings(_env_file=None),
    )

    output = await graph.ainvoke(
        {
            "question": "Did this company generate a demand?",
            "messages": [
                HumanMessage(content="Did this company generate a demand?")
            ],
            "error": "",
        },
        config={"configurable": {"thread_id": "clarify-thread"}},
    )

    assert output["final_response"] == "Which company do you mean?"
    assert output.get("query_results", []) == []


def test_error_handler_does_not_expose_internal_guardrail_reason() -> None:
    result = handle_error(
        {
            "sql_error": 'Column "password" is blocked.',
            "error": "Query execution was blocked.",
        }
    )

    assert "password" not in result["final_response"]
    assert "blocked" not in result["final_response"]
