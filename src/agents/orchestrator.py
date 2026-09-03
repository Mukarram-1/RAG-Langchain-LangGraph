"""Intent-routing agent."""

import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.conversation import recent_turns
from src.models.schemas import Intent, RouteDecision
from src.prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT
from src.state import AgentState

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Classify requests into explicit, graph-controlled routes."""

    def __init__(self, model: BaseChatModel) -> None:
        self._model = model.with_structured_output(RouteDecision)

    async def __call__(self, state: AgentState) -> dict[str, Any]:
        question = state.get("question", "").strip()
        if not question:
            return {
                "intent": Intent.OUT_OF_SCOPE.value,
                "intent_reason": "No question was provided.",
                "error": "A non-empty question is required.",
            }

        try:
            raw_decision = await self._model.ainvoke(
                [
                    SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
                    *recent_turns(state),
                    HumanMessage(content=question),
                ]
            )
            decision = (
                raw_decision
                if isinstance(raw_decision, RouteDecision)
                else RouteDecision.model_validate(raw_decision)
            )
            logger.info(
                "[orchestrator] intent=%s reason=%s",
                decision.intent.value,
                decision.reason,
            )
            return {
                "intent": decision.intent.value,
                "intent_reason": decision.reason,
            }
        except Exception:
            logger.exception("Orchestrator invocation failed")
            return {
                "intent": Intent.OUT_OF_SCOPE.value,
                "intent_reason": "Routing was unavailable.",
                "error": "The request could not be classified.",
            }
