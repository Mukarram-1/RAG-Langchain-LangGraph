"""Pass 2 model critic for query-result grounding."""

import json
import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.models.schemas import (
    GroundingVerdict,
    ValidationDecision,
)
from src.prompts.result_validator import RESULT_VALIDATOR_SYSTEM_PROMPT
from src.state import AgentState

logger = logging.getLogger(__name__)

RETRYABLE_VERDICTS = {
    GroundingVerdict.INSUFFICIENT,
    GroundingVerdict.EMPTY_UNCLEAR,
}


class ResultValidatorAgent:
    """Grade confirmed rows before any staff-facing prose is written."""

    def __init__(self, model: BaseChatModel, max_retries: int = 2) -> None:
        self._model = model.with_structured_output(ValidationDecision)
        self._max_retries = max_retries

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        payload = {
            "question": state.get("question", ""),
            "executed_sql": state.get("generated_sql", ""),
            "sql_rationale": state.get("sql_rationale", ""),
            "tables": state.get("referenced_tables", []),
            "deterministic_checks": state.get("checks_note", ""),
            "row_count": state.get("row_count", 0),
            "row_sample": state.get("query_results", [])[:20],
        }
        try:
            raw = await self._model.ainvoke(
                [
                    SystemMessage(content=RESULT_VALIDATOR_SYSTEM_PROMPT),
                    HumanMessage(
                        content=json.dumps(
                            payload,
                            ensure_ascii=False,
                            default=str,
                        )
                    ),
                ]
            )
            decision = (
                raw
                if isinstance(raw, ValidationDecision)
                else ValidationDecision.model_validate(raw)
            )
        except Exception:
            logger.exception("Result validator invocation failed")
            return {
                "validation_verdict": GroundingVerdict.INSUFFICIENT.value,
                "validation_reason": "Grounding validation was unavailable.",
                "retry_requested": False,
                "error": "The lookup result could not be validated.",
            }

        retry_count = state.get("retry_count", 0)
        retry_requested = (
            decision.verdict in RETRYABLE_VERDICTS
            and retry_count < self._max_retries
        )
        if retry_requested:
            retry_count += 1
        feedback = ""
        if retry_requested:
            feedback = (
                f"Result critic verdict: {decision.verdict.value}. "
                f"Reason: {decision.reason}. "
                f"Advice: {decision.retry_advice}"
            )
        logger.info(
            "[result_validator] verdict=%s retry=%s reason=%s",
            decision.verdict.value,
            retry_requested,
            decision.reason,
        )
        return {
            "validation_verdict": decision.verdict.value,
            "validation_reason": decision.reason,
            "retry_advice": decision.retry_advice,
            "retry_requested": retry_requested,
            "retry_count": retry_count,
            "guardrail_feedback": feedback,
            "error": "",
        }
