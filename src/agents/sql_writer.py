"""Structured lookup agent that drafts schema-scoped SQL."""

import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.conversation import recent_turns
from src.db.schema_loader import SchemaCatalog
from src.models.schemas import DraftStatus, SQLDraft
from src.prompts.sql_writer import SQL_WRITER_SYSTEM_PROMPT
from src.state import AgentState

logger = logging.getLogger(__name__)


class SQLWriterAgent:
    """Generate SQL but never connect to or execute against the database."""

    def __init__(
        self,
        model: BaseChatModel,
        schema_catalog: SchemaCatalog,
    ) -> None:
        self._model = model.with_structured_output(SQLDraft)
        self._system_prompt = SQL_WRITER_SYSTEM_PROMPT.format(
            schema_manifest=schema_catalog.to_prompt()
        )

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        question = state.get("question", "").strip()
        feedback = state.get("guardrail_feedback", "").strip()
        current_prompt = question
        if feedback:
            current_prompt += (
                "\n\nA previous attempt was rejected. Correct it using this "
                f"feedback:\n{feedback}\nPrevious SQL:\n"
                f"{state.get('generated_sql', '')}"
            )
        try:
            raw_draft = await self._model.ainvoke(
                [
                    SystemMessage(content=self._system_prompt),
                    *recent_turns(state),
                    HumanMessage(content=current_prompt),
                ]
            )
            draft = (
                raw_draft
                if isinstance(raw_draft, SQLDraft)
                else SQLDraft.model_validate(raw_draft)
            )
            sql = draft.sql.strip()
            logger.info(
                "[sql_writer] status=%s rationale=%s",
                draft.status.value,
                draft.rationale,
            )
            if sql:
                logger.info("[sql_writer] draft_sql=\n%s", sql)
            return {
                "draft_status": draft.status.value,
                "clarification": draft.clarification.strip(),
                "generated_sql": sql,
                "sql_rationale": draft.rationale,
                "sql_error": "",
                "retry_requested": False,
                "error": "",
            }
        except Exception:
            logger.exception("SQL writer invocation failed")
            return {
                "draft_status": DraftStatus.NEEDS_CLARIFICATION.value,
                "clarification": "",
                "generated_sql": "",
                "sql_valid": False,
                "sql_error": "SQL generation failed.",
                "error": "The structured lookup could not be generated.",
            }
