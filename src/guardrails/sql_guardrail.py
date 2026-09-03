"""AST-based SQL safety validation; no model is involved."""

import logging
import re
from typing import Any

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from src.db.schema_loader import SchemaCatalog, TableSchema
from src.models.schemas import GuardrailResult
from src.state import AgentState

logger = logging.getLogger(__name__)

COMMENT_PATTERN = re.compile(r"--|/\*", re.MULTILINE)
BLOCKED_COLUMNS = {
    "password",
    "password_hash",
    "resettoken",
    "rawpayload",
}
ALLOWED_FUNCTIONS = {
    "ABS",
    "AND",
    "AVG",
    "CAST",
    "CEIL",
    "COALESCE",
    "CONCAT",
    "COUNT",
    "DATE_TRUNC",
    "EXTRACT",
    "FLOOR",
    "GREATEST",
    "LENGTH",
    "LEAST",
    "LOWER",
    "MAX",
    "MIN",
    "NULLIF",
    "OR",
    "ROUND",
    "SUM",
    "UPPER",
}
PROHIBITED_NODES = (
    exp.Delete,
    exp.Insert,
    exp.Update,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
    exp.Copy,
    exp.Into,
)


class SQLGuardrail:
    """Validate generated SQL against an immutable schema allow-list."""

    def __init__(
        self,
        catalog: SchemaCatalog,
        max_rows: int,
    ) -> None:
        self._catalog = catalog
        self._max_rows = max_rows

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        result = self.validate(state.get("generated_sql", ""))
        retry_count = state.get("retry_count", 0)
        if not result.valid:
            retry_count += 1
        logger.info(
            "[sql_guardrail] valid=%s retry_count=%d tables=%s error=%s",
            result.valid,
            retry_count,
            result.referenced_tables,
            result.error or "none",
        )
        if result.valid:
            logger.info("[sql_guardrail] guarded_sql=\n%s", result.sql)
        return {
            "generated_sql": result.sql,
            "sql_valid": result.valid,
            "sql_error": result.error,
            "referenced_tables": result.referenced_tables,
            "guardrail_feedback": result.error if not result.valid else "",
            "retry_count": retry_count,
            "error": "",
        }

    def validate(self, sql: str) -> GuardrailResult:
        if not sql.strip():
            return self._invalid("No SQL was generated.")
        if COMMENT_PATTERN.search(sql):
            return self._invalid("SQL comments are not permitted.")

        try:
            statements = parse(sql, read="postgres")
        except ParseError:
            return self._invalid("The generated SQL could not be parsed.")

        if len(statements) != 1 or statements[0] is None:
            return self._invalid("Exactly one SQL statement is required.")

        statement = statements[0]
        if not isinstance(statement, exp.Select):
            return self._invalid("Only a SELECT statement is permitted.")
        if any(statement.find(node_type) for node_type in PROHIBITED_NODES):
            return self._invalid("The query contains a prohibited operation.")
        if statement.args.get("with_") or statement.find(exp.Subquery):
            return self._invalid("CTEs and subqueries are not permitted.")
        if statement.find(exp.Star):
            return self._invalid("SELECT * is not permitted.")
        if statement.args.get("locks"):
            return self._invalid("Row-locking clauses are not permitted.")

        function_error = self._validate_functions(statement)
        if function_error:
            return self._invalid(function_error)

        table_map, tables, table_error = self._validate_tables(statement)
        if table_error:
            return self._invalid(table_error)

        column_error = self._validate_columns(statement, table_map, tables)
        if column_error:
            return self._invalid(column_error)

        self._apply_limit(statement)
        guarded_sql = statement.sql(dialect="postgres", pretty=False)
        return GuardrailResult(
            valid=True,
            sql=guarded_sql,
            referenced_tables=[table.qualified_name for table in tables],
        )

    def _validate_tables(
        self,
        statement: exp.Select,
    ) -> tuple[dict[str, TableSchema], list[TableSchema], str]:
        table_map: dict[str, TableSchema] = {}
        referenced: list[TableSchema] = []

        for table_expression in statement.find_all(exp.Table):
            if not self._is_quoted(table_expression.this):
                return {}, [], f'Table "{table_expression.name}" must be quoted.'
            schema_name = table_expression.db or None
            if schema_name and not self._is_quoted(table_expression.args["db"]):
                return {}, [], f'Schema "{schema_name}" must be quoted.'

            table = self._catalog.find_table(
                table_expression.name,
                schema_name,
            )
            if table is None:
                label = (
                    f"{schema_name}.{table_expression.name}"
                    if schema_name
                    else table_expression.name
                )
                return {}, [], f'Table "{label}" is not allowed.'

            alias = table_expression.alias
            table_map[alias or table.name] = table
            table_map[table.name] = table
            if table not in referenced:
                referenced.append(table)

        return table_map, referenced, ""

    def _validate_columns(
        self,
        statement: exp.Select,
        table_map: dict[str, TableSchema],
        tables: list[TableSchema],
    ) -> str:
        output_aliases = {
            item.alias
            for item in statement.expressions
            if item.alias
        }
        for column in statement.find_all(exp.Column):
            name = column.name
            if name.lower() in BLOCKED_COLUMNS:
                return f'Column "{name}" is blocked.'
            if not self._is_quoted(column.this):
                return f'Column "{name}" must be quoted.'
            if name in output_aliases:
                continue

            if column.table:
                table = table_map.get(column.table)
                if table is None:
                    return f'Unknown table or alias "{column.table}".'
                if name not in table.columns:
                    return f'Column "{name}" is not in table "{table.name}".'
                continue

            matches = [table for table in tables if name in table.columns]
            if len(matches) == 0:
                return f'Column "{name}" is not in an allowed table.'
            if len(matches) > 1:
                return f'Column "{name}" is ambiguous; qualify it with a table.'
        return ""

    @staticmethod
    def _validate_functions(statement: exp.Select) -> str:
        for function in statement.find_all(exp.Func):
            name = function.sql_name().upper()
            if name not in ALLOWED_FUNCTIONS:
                return f'Function "{name}" is not permitted.'
        return ""

    def _apply_limit(self, statement: exp.Select) -> None:
        limit = statement.args.get("limit")
        requested = self._max_rows
        if limit is not None and isinstance(limit.expression, exp.Literal):
            try:
                requested = min(int(limit.expression.this), self._max_rows)
            except (TypeError, ValueError):
                requested = self._max_rows
        statement.limit(max(1, requested), copy=False)

    @staticmethod
    def _is_quoted(identifier: exp.Expression) -> bool:
        return isinstance(identifier, exp.Identifier) and bool(
            identifier.args.get("quoted")
        )

    @staticmethod
    def _invalid(message: str) -> GuardrailResult:
        return GuardrailResult(valid=False, error=message)
