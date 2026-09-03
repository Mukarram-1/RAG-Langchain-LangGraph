"""Deterministic result-check tests."""

import pytest

from src.validation.result_checks import ResultChecks


@pytest.mark.asyncio
async def test_marks_empty_results() -> None:
    result = await ResultChecks(max_rows=100)(
        {"query_results": [], "row_count": 0}
    )

    assert result["result_empty"] is True
    assert result["result_truncated"] is False
    assert "no rows" in result["checks_note"]


@pytest.mark.asyncio
async def test_marks_truncation_and_all_null_rows() -> None:
    rows = [{"value": None} for _ in range(2)]
    result = await ResultChecks(max_rows=2)(
        {"query_results": rows, "row_count": 2}
    )

    assert result["result_truncated"] is True
    assert result["all_values_null"] is True
    assert "may be incomplete" in result["checks_note"]
