"""Blocks real network access for every test under tests/unit/routing/ (FR-019, constitution
Principle V: "A test MUST NEVER make a real API call"). respx already intercepts httpx at the
transport layer for every OSRM-touching test here, so this never fires in the passing case; it
exists to fail loudly, not silently pass over real traffic, if a test is ever missing its
`@respx.mock` decorator. Same pattern as tests/integration/test_build_data_command.py.
"""

import socket
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _block_real_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    yield
