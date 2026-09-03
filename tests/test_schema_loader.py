"""Schema and relationship metadata tests."""

from typing import Any

import pytest

from src.db.schema_loader import load_schema_catalog


class FakeDatabase:
    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if "information_schema.columns" in query:
            return [
                {
                    "table_schema": "public",
                    "table_name": "Domain",
                    "column_name": "id",
                    "data_type": "uuid",
                    "is_nullable": "NO",
                },
                {
                    "table_schema": "public",
                    "table_name": "Litigation",
                    "column_name": "domainId",
                    "data_type": "uuid",
                    "is_nullable": "NO",
                },
            ]
        return [
            {
                "source_schema": "public",
                "source_table": "Litigation",
                "source_column": "domainId",
                "target_schema": "public",
                "target_table": "Domain",
                "target_column": "id",
            }
        ]


@pytest.mark.asyncio
async def test_schema_prompt_contains_relations_and_business_semantics() -> None:
    catalog = await load_schema_catalog(
        FakeDatabase(),  # type: ignore[arg-type]
        ("public",),
    )

    prompt = catalog.to_prompt()

    assert len(catalog.relationships) == 1
    assert '"Litigation"."domainId"' in prompt
    assert '"Domain"."id"' in prompt
    assert '"retestVisiteDate"' in prompt
    assert "one physical-location legal case" in prompt
    assert '"Domain"."client" joins "Client"."id"' in prompt
    assert '"Location"."client"' in prompt
    assert '"PhysicalClient"."id"' in prompt
    assert '"Settlements"."domain"' in prompt
