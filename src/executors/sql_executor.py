"""Execute only guardrail-approved SQL on the read-only pool."""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.db.connection import Database
from src.state import AgentState

logger = logging.getLogger(__name__)


class SQLExecutor:
    """Thin execution boundary with no SQL generation capability."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        if not state.get("sql_valid", False):
            logger.warning(
                "[sql_executor] blocked unvalidated SQL: %s",
                state.get("sql_error", "no guardrail reason"),
            )
            return {
                "query_results": [],
                "row_count": 0,
                "error": "Query execution was blocked.",
            }

        sql = state.get("generated_sql", "")
        try:
            logger.info("[sql_executor] executing guardrailed SQL")
            records = await self._database.fetch(sql)
            rows = [
                {
                    key: _to_serializable(value)
                    for key, value in dict(record).items()
                }
                for record in records
            ]
            logger.info(
                "[sql_executor] completed row_count=%d",
                len(rows),
            )
            return {
                "query_results": rows,
                "row_count": len(rows),
                "error": "",
            }
        except Exception:
            logger.exception("Guardrailed SQL execution failed")
            return {
                "query_results": [],
                "row_count": 0,
                "error": "The database query could not be completed.",
            }


def _to_serializable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, UUID)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    if isinstance(value, bytes):
        return f"<binary:{len(value)} bytes>"
    if isinstance(value, dict):
        return {
            str(key): _to_serializable(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_to_serializable(item) for item in value]
    return str(value)
