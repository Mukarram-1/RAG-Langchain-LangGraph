"""Cheap deterministic checks before the grounding critic."""

import logging
from typing import Any

from src.state import AgentState

logger = logging.getLogger(__name__)


class ResultChecks:
    """Annotate query results without making semantic claims."""

    def __init__(self, max_rows: int) -> None:
        self._max_rows = max_rows

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        rows = state.get("query_results", [])
        row_count = state.get("row_count", len(rows))
        result_empty = row_count == 0
        result_truncated = row_count >= self._max_rows
        all_values_null = bool(rows) and all(
            all(value is None for value in row.values())
            for row in rows
        )

        notes: list[str] = []
        if result_empty:
            notes.append("The query returned no rows.")
        if result_truncated:
            notes.append(
                f"The result reached the {self._max_rows}-row safety limit "
                "and may be incomplete."
            )
        if all_values_null:
            notes.append("Every returned value is null.")
        if not notes:
            notes.append(
                f"The query returned {row_count} row(s) within the safety limit."
            )
        checks_note = " ".join(notes)
        logger.info("[result_checks] %s", checks_note)
        return {
            "checks_note": checks_note,
            "result_empty": result_empty,
            "result_truncated": result_truncated,
            "all_values_null": all_values_null,
        }
