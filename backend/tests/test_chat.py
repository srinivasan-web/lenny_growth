from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

from app.services.chat import ChatService


class FailingDatabase:
    def add(self, message: object) -> None:
        pass

    async def commit(self) -> None:
        raise RuntimeError("database unavailable")

    async def rollback(self) -> None:
        pass


class UnusedRAG:
    async def stream(self, query: str) -> AsyncIterator[object]:
        yield object()


@pytest.mark.asyncio
async def test_unexpected_stream_failure_emits_terminal_error() -> None:
    events = [event async for event in ChatService(FailingDatabase(), UnusedRAG()).stream(uuid4(), "activation")]

    assert events[-1].startswith("event: error")
    assert "could not complete" in events[-1]