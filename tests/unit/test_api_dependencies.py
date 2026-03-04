"""Tests for FastAPI dependency functions."""

from unittest.mock import MagicMock

from backend.api.dependencies import get_client, get_session_store
from backend.tally_bridge.client import TallyClient
from backend.agents.context import SessionStore


def test_get_client_returns_client_from_app_state():
    mock_request = MagicMock()
    mock_request.app.state.tally_client = TallyClient("localhost", 9000)
    result = get_client(mock_request)
    assert isinstance(result, TallyClient)


def test_get_session_store_returns_store_from_app_state():
    mock_request = MagicMock()
    mock_request.app.state.session_store = SessionStore(ttl_minutes=60)
    result = get_session_store(mock_request)
    assert isinstance(result, SessionStore)
