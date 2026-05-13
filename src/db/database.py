from __future__ import annotations

import asyncpg


class Database:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def execute(self, query: str, *args) -> str:
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args) -> list[asyncpg.Record]:
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args) -> asyncpg.Record | None:
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
