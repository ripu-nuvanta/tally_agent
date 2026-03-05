"""Session context and in-memory session store for conversation management."""

import time
import uuid

from backend.config import settings


class SessionContext:
    """Tracks conversation state for a single user session."""

    def __init__(
        self,
        session_id: str | None = None,
        company: str | None = None,
        max_messages: int = 20,
    ) -> None:
        self.session_id: str = session_id or str(uuid.uuid4())
        self.company: str | None = company
        self.messages: list[dict] = []
        self.created_at: float = time.time()
        self.last_activity: float = time.time()
        self._max_messages: int = max_messages

    def add_message(self, role: str, content: str) -> None:
        """Append a message and trim to max_messages (keeping the most recent)."""
        self.messages.append({"role": role, "content": content})
        self.last_activity = time.time()
        if len(self.messages) > self._max_messages:
            self.messages = self.messages[-self._max_messages :]

    def get_messages(self) -> list[dict]:
        """Return a shallow copy of the messages list."""
        return list(self.messages)


class SessionStore:
    """In-memory store of session contexts with TTL-based expiry."""

    def __init__(self, ttl_minutes: int = settings.SESSION_TTL_MINUTES) -> None:
        self._sessions: dict[str, SessionContext] = {}
        self._ttl_seconds: float = ttl_minutes * 60

    def cleanup_expired(self) -> None:
        """Remove all sessions whose last_activity exceeds the TTL."""
        now = time.time()
        expired = [
            sid
            for sid, ctx in self._sessions.items()
            if now - ctx.last_activity > self._ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]

    def get_or_create(
        self,
        session_id: str | None = None,
        company: str | None = None,
    ) -> SessionContext:
        """Return an existing session or create a new one.

        - If session_id exists and is not expired, return it (updating company if provided).
        - If session_id exists but is expired, delete it and create a new one.
        - If no session_id is given, create a new session.
        """
        if len(self._sessions) > 100:
            self.cleanup_expired()

        if session_id and session_id in self._sessions:
            ctx = self._sessions[session_id]
            if time.time() - ctx.last_activity > self._ttl_seconds:
                del self._sessions[session_id]
            else:
                if company is not None:
                    ctx.company = company
                return ctx

        ctx = SessionContext(session_id=session_id, company=company)
        self._sessions[ctx.session_id] = ctx
        return ctx
