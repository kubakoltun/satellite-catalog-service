"""Lekkie podstawki (test doubles) pod asyncpg - bez realnej bazy danych.

Próbuję mockować tylko wąski wycinek API, którego używa `PgstacRepository`: `pool.acquire()` 
jako async context manager i `conn.execute(sql, *args)`. To pozwala
przetestować logikę repozytorium (jakie zapytanie leci, jak wygląda
payload, jak mapowane są błędy) bez podnoszenia Postgresa - realny zapis
do pgSTAC sprawdza dopiero test integracyjny (`tests/integration/`).
"""

from __future__ import annotations


class FakeConnection:
    def __init__(
        self,
        *,
        raise_error: Exception | None = None,
        fetchval_result: object = None,
    ) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self._raise_error = raise_error
        self._fetchval_result = fetchval_result

    async def execute(self, sql: str, *args) -> None:
        self.calls.append((sql, args))
        if self._raise_error is not None:
            raise self._raise_error

    async def fetchval(self, sql: str, *args):
        self.calls.append((sql, args))
        if self._raise_error is not None:
            raise self._raise_error
        return self._fetchval_result


class _AcquireContext:
    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    async def __aenter__(self) -> FakeConnection:
        return self._conn

    async def __aexit__(self, *exc_info) -> bool:
        return False


class FakePool:
    def __init__(self, conn: FakeConnection) -> None:
        self._conn = conn

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self._conn)
