"""Load a safe schema manifest from PostgreSQL metadata."""

from dataclasses import dataclass
import logging

from src.db.business_metadata import BUSINESS_GLOSSARY
from src.db.connection import Database

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool


@dataclass(frozen=True, slots=True)
class TableSchema:
    schema: str
    name: str
    columns: dict[str, ColumnSchema]

    @property
    def qualified_name(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True, slots=True)
class ForeignKeySchema:
    source_schema: str
    source_table: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str

    def to_prompt(self) -> str:
        return (
            f'"{self.source_schema}"."{self.source_table}"."{self.source_column}"'
            f' -> "{self.target_schema}"."{self.target_table}".'
            f'"{self.target_column}"'
        )


@dataclass(frozen=True, slots=True)
class SchemaCatalog:
    """Immutable table/column allow-list used by prompts and guardrails."""

    tables: dict[str, TableSchema]
    relationships: tuple[ForeignKeySchema, ...] = ()

    def find_table(
        self,
        table_name: str,
        schema_name: str | None = None,
    ) -> TableSchema | None:
        if schema_name:
            return self.tables.get(f"{schema_name}.{table_name}")

        matches = [
            table
            for table in self.tables.values()
            if table.name == table_name
        ]
        return matches[0] if len(matches) == 1 else None

    def to_prompt(self) -> str:
        """Render only metadata; never include table rows or credentials."""
        table_sections: list[str] = []
        for table in sorted(
            self.tables.values(),
            key=lambda item: (item.schema, item.name),
        ):
            columns = ", ".join(
                f'"{column.name}" {column.data_type}'
                for column in table.columns.values()
            )
            table_sections.append(
                f'- "{table.schema}"."{table.name}" ({columns})'
            )
        relationship_sections = [
            f"- {relationship.to_prompt()}"
            for relationship in self.relationships
        ]
        relationships = (
            "\n".join(relationship_sections)
            if relationship_sections
            else "- No declared foreign keys were discovered."
        )
        return (
            "TABLES AND COLUMNS:\n"
            + "\n".join(table_sections)
            + "\n\nDECLARED RELATIONSHIPS (join only on these pairs unless "
            "the business glossary explicitly states another relation):\n"
            + relationships
            + "\n\nBUSINESS GLOSSARY:\n"
            + BUSINESS_GLOSSARY
        )


SCHEMA_QUERY = """
SELECT
    table_schema,
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = ANY($1::text[])
ORDER BY table_schema, table_name, ordinal_position
"""

FOREIGN_KEY_QUERY = """
SELECT
    tc.table_schema AS source_schema,
    tc.table_name AS source_table,
    kcu.column_name AS source_column,
    ccu.table_schema AS target_schema,
    ccu.table_name AS target_table,
    ccu.column_name AS target_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_catalog = kcu.constraint_catalog
 AND tc.constraint_schema = kcu.constraint_schema
 AND tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON tc.constraint_catalog = ccu.constraint_catalog
 AND tc.constraint_schema = ccu.constraint_schema
 AND tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = ANY($1::text[])
  AND ccu.table_schema = ANY($1::text[])
ORDER BY
    tc.table_schema,
    tc.table_name,
    kcu.ordinal_position
"""


async def load_schema_catalog(
    database: Database,
    allowed_schemas: tuple[str, ...],
) -> SchemaCatalog:
    """Introspect only configured schemas and build an allow-list."""
    if not allowed_schemas:
        raise ValueError("At least one SQL_ALLOWED_SCHEMAS value is required")

    schema_names = list(allowed_schemas)
    rows = await database.fetch(SCHEMA_QUERY, schema_names)
    foreign_key_rows = await database.fetch(
        FOREIGN_KEY_QUERY,
        schema_names,
    )
    mutable_tables: dict[str, dict[str, object]] = {}

    for row in rows:
        key = f"{row['table_schema']}.{row['table_name']}"
        table = mutable_tables.setdefault(
            key,
            {
                "schema": row["table_schema"],
                "name": row["table_name"],
                "columns": {},
            },
        )
        columns = table["columns"]
        assert isinstance(columns, dict)
        columns[row["column_name"]] = ColumnSchema(
            name=row["column_name"],
            data_type=row["data_type"],
            nullable=row["is_nullable"] == "YES",
        )

    tables = {
        key: TableSchema(
            schema=str(data["schema"]),
            name=str(data["name"]),
            columns=data["columns"],  # type: ignore[arg-type]
        )
        for key, data in mutable_tables.items()
    }
    if not tables:
        joined = ", ".join(allowed_schemas)
        raise RuntimeError(f"No tables found in configured schemas: {joined}")

    relationships = tuple(
        ForeignKeySchema(
            source_schema=row["source_schema"],
            source_table=row["source_table"],
            source_column=row["source_column"],
            target_schema=row["target_schema"],
            target_table=row["target_table"],
            target_column=row["target_column"],
        )
        for row in foreign_key_rows
    )
    logger.info(
        "[schema_loader] loaded %d tables and %d foreign-key relationships",
        len(tables),
        len(relationships),
    )
    return SchemaCatalog(tables=tables, relationships=relationships)
