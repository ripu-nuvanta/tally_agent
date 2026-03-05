"""Fixtures for live E2E tests against real Tally + real Claude API.

Gated by RUN_LIVE_TESTS=1 environment variable.
Requires ANTHROPIC_API_KEY and a reachable Tally instance.
"""

import os

import pytest

from backend.tally_bridge.client import TallyClient
from backend.agents.orchestrator import Orchestrator
from backend.agents.context import SessionStore


def pytest_addoption(parser):
    parser.addoption("--host", default=os.environ.get("TALLY_HOST", "localhost"))
    parser.addoption("--port", type=int, default=int(os.environ.get("TALLY_PORT", "9000")))


pytestmark = pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_TESTS"),
    reason="RUN_LIVE_TESTS not set — skipping live E2E tests",
)


@pytest.fixture(scope="session")
def tally_host(request):
    return request.config.getoption("--host")


@pytest.fixture(scope="session")
def tally_port(request):
    return request.config.getoption("--port")


@pytest.fixture(scope="session")
async def tally_client(tally_host, tally_port):
    """Real TallyClient connected to a live Tally instance."""
    client = TallyClient(host=tally_host, port=tally_port)
    healthy = await client.health_check()
    if not healthy:
        pytest.skip(f"Tally unreachable at {tally_host}:{tally_port}")
    yield client
    await client.close()


@pytest.fixture
def orchestrator():
    return Orchestrator()


@pytest.fixture
def session_store():
    return SessionStore()


@pytest.fixture
def session(session_store):
    return session_store.get_or_create()
