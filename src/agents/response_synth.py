"""Pass 3 grounded natural-language response synthesis."""

import json
import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.models.schemas import SynthesizedAnswer
from src.prompts.response_synth import RESPONSE_SYNTH_SYSTEM_PROMPT
from src.state import AgentState

logger = logging.getLogger(__name__)


class ResponseSynthAgent:
    """Render validated rows without introducing unsupported facts."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(SynthesizedAnswer)

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        payload = {
            "question": state.get("question", ""),
            "rows": state.get("query_results", []),
            "row_count": state.get("row_count", 0),
            "source_tables": state.get("referenced_tables", []),
            "result_truncated": state.get("result_truncated", False),
            "validation_verdict": state.get("validation_verdict", ""),
            "validation_reason": state.get("validation_reason", ""),
            "retries_used": state.get("retry_count", 0),
        }
        try:
            raw = await self._model.ainvoke(
                [
                    SystemMessage(content=RESPONSE_SYNTH_SYSTEM_PROMPT),
                    HumanMessage(
                        content=json.dumps(
                            payload,
                            ensure_ascii=False,
                            default=str,
                        )
                    ),
                ]
            )
            result = (
                raw
                if isinstance(raw, SynthesizedAnswer)
                else SynthesizedAnswer.model_validate(raw)
            )
            answer = result.answer.strip()
            logger.info("[response_synth] generated grounded response")
            return {
                "final_response": answer,
                "messages": [AIMessage(content=answer)],
                "error": "",
            }
        except Exception:
            logger.exception("Response synthesis failed")
            answer = (
                "The lookup completed, but a grounded response could not "
                "be produced. Please try again."
            )
            return {
                "final_response": answer,
                "messages": [AIMessage(content=answer)],
                "error": "Response synthesis failed.",
            }
