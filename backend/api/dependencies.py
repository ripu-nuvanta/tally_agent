"""FastAPI dependency functions for injecting shared resources."""

from fastapi import Request

from backend.agents.context import SessionStore
from backend.tally_bridge.client import TallyClient


def get_client(request: Request) -> TallyClient:
    """Return the app-level TallyClient singleton."""
    return request.app.state.tally_client


def get_session_store(request: Request) -> SessionStore:
    """Return the app-level SessionStore singleton."""
    return request.app.state.session_store
