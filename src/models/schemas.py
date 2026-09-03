"""Pydantic contracts at agent and infrastructure boundaries."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Intent(StrEnum):
    STRUCTURED_LOOKUP = "structured_lookup"
    RAG_SEARCH = "rag_search"
    OUT_OF_SCOPE = "out_of_scope"


class DraftStatus(StrEnum):
    OK = "ok"
    NEEDS_CLARIFICATION = "needs_clarification"


class GroundingVerdict(StrEnum):
    OK = "ok"
    INSUFFICIENT = "insufficient"
    CONTRADICTS = "contradicts"
    EMPTY_UNCLEAR = "empty_unclear"


class RouteDecision(BaseModel):
    """Structured output from the orchestrator."""

    model_config = ConfigDict(extra="forbid")

    intent: Intent
    reason: str = Field(
        min_length=1,
        max_length=300,
        description="Brief routing explanation without hidden reasoning.",
    )


class SQLDraft(BaseModel):
    """Structured output from the SQL writer."""

    model_config = ConfigDict(extra="forbid")

    status: DraftStatus = DraftStatus.OK
    sql: str = Field(default="", description="One PostgreSQL SELECT statement.")
    rationale: str = Field(
        min_length=1,
        max_length=500,
        description="Short description of the query's purpose.",
    )
    clarification: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_status_fields(self) -> "SQLDraft":
        if self.status == DraftStatus.OK and not self.sql.strip():
            raise ValueError("sql is required when status is ok")
        if (
            self.status == DraftStatus.NEEDS_CLARIFICATION
            and not self.clarification.strip()
        ):
            raise ValueError(
                "clarification is required when status needs clarification"
            )
        return self


class ValidationDecision(BaseModel):
    """Structured output from the grounding critic."""

    model_config = ConfigDict(extra="forbid")

    verdict: GroundingVerdict

    reason: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Concise explanation of the verdict. "
            "Maximum 500 characters. Use 1-3 short sentences. "
            "Do not repeat the SQL."
        ),
    )

    retry_advice: str = Field(
        default="",
        max_length=500,
        description=(
            "Concise advice for correcting the query/result if a retry is needed. "
            "Maximum 500 characters."
        ),
    )


class SynthesizedAnswer(BaseModel):
    """Grounded staff-facing answer."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=8_000)


class GuardrailResult(BaseModel):
    """Outcome of deterministic SQL validation."""

    valid: bool
    sql: str = ""
    error: str = ""
    referenced_tables: list[str] = Field(default_factory=list)


class QueryExecutionResult(BaseModel):
    """Serializable result returned by the SQL executor."""

    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    error: str = ""


class ChatResult(BaseModel):
    """Public result returned by the framework."""

    answer: str
    intent: Intent
    generated_sql: str = ""
    row_count: int = 0
    error: str = ""
