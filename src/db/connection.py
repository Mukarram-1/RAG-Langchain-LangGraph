"""Lifecycle-managed, read-only PostgreSQL connection pool."""

from collections.abc import Sequence
from typing import Any

import asyncpg

from src.config import Settings


class Database:
    """Own an asyncpg pool and expose only read operations."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    @property
    def is_started(self) -> bool:
        return self._pool is not None

    async def start(self) -> None:
        if self._pool is not None:
            return

        self._pool = await asyncpg.create_pool(
            dsn=self._settings.require_database_url(),
            min_size=self._settings.db_pool_min_size,
            max_size=self._settings.db_pool_max_size,
            command_timeout=self._settings.db_command_timeout_seconds,
            server_settings={
                "application_name": "legal_ai_chatbot",
                "default_transaction_read_only": "on",
                "statement_timeout": str(
                    self._settings.db_statement_timeout_ms
                ),
            },
        )

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def fetch(
        self,
        query: str,
        *args: Any,
    ) -> list[asyncpg.Record]:
        if self._pool is None:
            raise RuntimeError("Database pool has not been started")
        return await self._pool.fetch(query, *args)

    async def fetch_with_parameters(
        self,
        query: str,
        parameters: Sequence[Any],
    ) -> list[asyncpg.Record]:
        return await self.fetch(query, *parameters)
