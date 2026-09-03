"""Bounded retry and feedback tests."""

from typing import Any

import pytest
from langchain_core.runnables import RunnableLambda

from src.agents.sql_writer import SQLWriterAgent
from src.db.schema_loader import ColumnSchema, SchemaCatalog, TableSchema
from src.graph import route_after_guardrail
from src.guardrails.sql_guardrail import SQLGuardrail
from src.models.schemas import SQLDraft


def make_catalog() -> SchemaCatalog:
    table = TableSchema(
        schema="public",
        name="Domain",
        columns={"id": ColumnSchema("id", "uuid", False)},
    )
    return SchemaCatalog(tables={table.qualified_name: table})


@pytest.mark.asyncio
async def test_guardrail_retries_twice_then_stops() -> None:
    guardrail = SQLGuardrail(make_catalog(), max_rows=100)
    state: dict[str, Any] = {
        "generated_sql": 'SELECT "missing" FROM "public"."Domain"',
        "retry_count": 0,
    }

    first = await guardrail(state)  # type: ignore[arg-type]
    assert first["retry_count"] == 1
    assert route_after_guardrail(first) == "sql_writer"  # type: ignore[arg-type]

    second = await guardrail(first)  # type: ignore[arg-type]
    assert second["retry_count"] == 2
    assert route_after_guardrail(second) == "sql_writer"  # type: ignore[arg-type]

    third = await guardrail(second)  # type: ignore[arg-type]
    assert third["retry_count"] == 3
    assert route_after_guardrail(third) == "error_handler"  # type: ignore[arg-type]
    assert third["error"] == ""


class RecordingModel:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    def with_structured_output(self, _: type[Any]) -> RunnableLambda:
        async def respond(messages: list[Any]) -> SQLDraft:
            self.messages = messages
            return SQLDraft(
                sql='SELECT "id" FROM "public"."Domain"',
                rationale="Corrected query.",
            )

        return RunnableLambda(respond)


@pytest.mark.asyncio
async def test_sql_writer_receives_rejection_feedback() -> None:
    model = RecordingModel()
    writer = SQLWriterAgent(model, make_catalog())  # type: ignore[arg-type]

    await writer(
        {
            "question": "Find the domain",
            "guardrail_feedback": 'Column "missing" is not allowed.',
            "generated_sql": 'SELECT "missing" FROM "public"."Domain"',
        }
    )

    last_message = model.messages[-1]
    assert "previous attempt was rejected" in str(last_message.content).lower()
    assert 'Column "missing"' in str(last_message.content)
