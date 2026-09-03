"""SQL executor boundary tests."""

from typing import Any

import pytest

from src.executors.sql_executor import SQLExecutor


class FakeDatabase:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.queries.append(query)
        return [{"amount": 10, "payload": b"abc"}]


@pytest.mark.asyncio
async def test_executor_runs_only_validated_sql() -> None:
    database = FakeDatabase()
    executor = SQLExecutor(database)  # type: ignore[arg-type]

    result = await executor(
        {
            "sql_valid": True,
            "generated_sql": 'SELECT "id" FROM "public"."Domain" LIMIT 1',
        }
    )

    assert len(database.queries) == 1
    assert result["row_count"] == 1
    assert result["query_results"][0]["payload"] == "<binary:3 bytes>"


@pytest.mark.asyncio
async def test_executor_refuses_unvalidated_sql() -> None:
    database = FakeDatabase()
    executor = SQLExecutor(database)  # type: ignore[arg-type]

    result = await executor(
        {
            "sql_valid": False,
            "generated_sql": 'DELETE FROM "public"."Domain"',
            "sql_error": "Rejected.",
        }
    )

    assert database.queries == []
    assert result["row_count"] == 0
