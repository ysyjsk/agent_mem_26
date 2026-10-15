"""Regression tests for the isolated AgentRunbook-R async-client fix.

Run from the repository root with:

    PYTHONPATH=runs/agentrunbook-r-native-small-20261014/async-fix-runtime \\
      /data/predator/ly/Mem/.venv/bin/python -m pytest -q \\
      runs/agentrunbook-r-native-small-20261014/async-fix-runtime/test_async_client_lifecycle.py

The test never contacts a model service. It exercises the exact synchronous
_run_async bridge used once per trajectory and verifies that a client is
closed on the same event loop that used it, including an exception path.
"""

from __future__ import annotations

import asyncio

import pytest

# Import the registry module first, matching the official evaluation harness.
# Importing agentrunbook_r directly would enter the registry's late imports
# while the class itself is still being defined and would look circular.
from memory_modules import memory as _memory_registry  # noqa: F401
from memory_modules.agentrunbook_r import AgentRunbookR


class _FakeAsyncClient:
    def __init__(self) -> None:
        self.created_loop = asyncio.get_running_loop()
        self.closed_loop = None
        self.closed = False

    async def close(self) -> None:
        self.closed_loop = asyncio.get_running_loop()
        self.closed = True


def _bare_memory() -> AgentRunbookR:
    memory = object.__new__(AgentRunbookR)
    memory._async_controller_client = None
    return memory


def test_run_async_closes_and_clears_client_per_event_loop() -> None:
    memory = _bare_memory()
    clients: list[_FakeAsyncClient] = []

    async def trajectory_batch() -> object:
        client = _FakeAsyncClient()
        clients.append(client)
        memory._async_controller_client = client
        await asyncio.sleep(0)
        return asyncio.get_running_loop()

    first_loop = memory._run_async(trajectory_batch())
    second_loop = memory._run_async(trajectory_batch())

    assert first_loop is not second_loop
    assert len(clients) == 2
    assert all(client.closed for client in clients)
    assert all(client.closed_loop is client.created_loop for client in clients)
    assert memory._async_controller_client is None


def test_run_async_closes_client_when_batch_raises() -> None:
    memory = _bare_memory()
    client_holder: list[_FakeAsyncClient] = []

    async def failing_batch() -> None:
        client = _FakeAsyncClient()
        client_holder.append(client)
        memory._async_controller_client = client
        raise ValueError("synthetic extraction failure")

    with pytest.raises(ValueError, match="synthetic extraction failure"):
        memory._run_async(failing_batch())

    client = client_holder[0]
    assert client.closed
    assert client.closed_loop is client.created_loop
    assert memory._async_controller_client is None
