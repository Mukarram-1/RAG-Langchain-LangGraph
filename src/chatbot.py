"""Reusable application lifecycle for CLI and future API adapters."""

from uuid import uuid4

from langchain_core.messages import HumanMessage

from src.config import Settings, get_chat_model, get_settings
from src.db.connection import Database
from src.db.schema_loader import load_schema_catalog
from src.graph import build_graph
from src.models.schemas import ChatResult, Intent


class LegalAIChatbot:
    """Start infrastructure once and process read-only lookup requests."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.database = Database(self.settings)
        self._graph = None

    async def start(self) -> None:
        if self._graph is not None:
            return
        await self.database.start()
        try:
            catalog = await load_schema_catalog(
                self.database,
                self.settings.allowed_schemas,
            )
            self._graph = build_graph(
                model=get_chat_model(self.settings),
                catalog=catalog,
                database=self.database,
                settings=self.settings,
            )
        except Exception:
            await self.database.close()
            raise

    async def close(self) -> None:
        self._graph = None
        await self.database.close()

    async def ask(
        self,
        question: str,
        thread_id: str | None = None,
    ) -> ChatResult:
        if self._graph is None:
            raise RuntimeError("Chatbot has not been started")

        normalized = question.strip()
        if not normalized:
            raise ValueError("Question must not be empty")

        output = await self._graph.ainvoke(
            {
                "question": normalized,
                "messages": [HumanMessage(content=normalized)],
                "error": "",
                "draft_status": "",
                "clarification": "",
                "sql_error": "",
                "guardrail_feedback": "",
                "retry_count": 0,
                "generated_sql": "",
                "sql_rationale": "",
                "sql_valid": False,
                "referenced_tables": [],
                "query_results": [],
                "row_count": 0,
                "checks_note": "",
                "result_empty": False,
                "result_truncated": False,
                "all_values_null": False,
                "validation_verdict": "",
                "validation_reason": "",
                "retry_advice": "",
                "retry_requested": False,
                "final_response": "",
            },
            config={
                "configurable": {
                    "thread_id": thread_id or str(uuid4()),
                },
                "recursion_limit": 30,
            },
        )
        return ChatResult(
            answer=output.get("final_response", "No response was produced."),
            intent=Intent(
                output.get("intent", Intent.OUT_OF_SCOPE)
            ),
            generated_sql=output.get("generated_sql", ""),
            row_count=output.get("row_count", 0),
            error=output.get("error", ""),
        )

    async def __aenter__(self) -> "LegalAIChatbot":
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
