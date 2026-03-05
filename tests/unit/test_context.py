"""Tests for session context and session store."""

import time

import pytest

from backend.agents.context import SessionContext, SessionStore
from backend.config import settings


class TestSessionContext:
    def test_create_with_defaults(self):
        ctx = SessionContext()
        assert ctx.session_id is not None
        assert len(ctx.session_id) == 36  # UUID format
        assert ctx.company is None
        assert ctx.messages == []
        assert ctx.created_at <= time.time()

    def test_create_with_company(self):
        ctx = SessionContext(company="Test Co")
        assert ctx.company == "Test Co"

    def test_create_with_session_id(self):
        ctx = SessionContext(session_id="my-session-123")
        assert ctx.session_id == "my-session-123"

    def test_add_user_message(self):
        ctx = SessionContext()
        ctx.add_message("user", "What is the trial balance?")
        assert len(ctx.messages) == 1
        assert ctx.messages[0] == {"role": "user", "content": "What is the trial balance?"}

    def test_add_assistant_message(self):
        ctx = SessionContext()
        ctx.add_message("assistant", "Here is the trial balance.")
        assert len(ctx.messages) == 1
        assert ctx.messages[0] == {"role": "assistant", "content": "Here is the trial balance."}

    def test_message_limit_enforced(self):
        ctx = SessionContext(max_messages=4)
        for i in range(6):
            ctx.add_message("user", f"Message {i}")
        assert len(ctx.messages) == 4
        # Should keep the last 4 messages (indices 2-5)
        assert ctx.messages[0]["content"] == "Message 2"
        assert ctx.messages[-1]["content"] == "Message 5"

    def test_get_messages_returns_copy(self):
        ctx = SessionContext()
        ctx.add_message("user", "Hello")
        msgs = ctx.get_messages()
        msgs.append({"role": "user", "content": "Extra"})
        assert len(ctx.messages) == 1  # Original unaffected


class TestSessionStore:
    def test_get_or_create_new(self):
        store = SessionStore()
        ctx = store.get_or_create()
        assert ctx.session_id is not None
        assert ctx.messages == []

    def test_get_existing(self):
        store = SessionStore()
        ctx1 = store.get_or_create()
        ctx1.add_message("user", "Hello")
        ctx2 = store.get_or_create(session_id=ctx1.session_id)
        assert ctx2 is ctx1
        assert len(ctx2.messages) == 1

    def test_get_existing_updates_company(self):
        store = SessionStore()
        ctx1 = store.get_or_create(company="Old Co")
        ctx2 = store.get_or_create(session_id=ctx1.session_id, company="New Co")
        assert ctx2.company == "New Co"

    def test_ttl_expiry(self):
        store = SessionStore(ttl_minutes=0)  # Immediate expiry
        ctx1 = store.get_or_create(session_id="expired-session")
        ctx1.add_message("user", "Hello")
        # Force last_activity into the past
        ctx1.last_activity = time.time() - 1
        ctx2 = store.get_or_create(session_id="expired-session")
        # Should be a new session (no messages)
        assert ctx2.session_id != ctx1.session_id or len(ctx2.messages) == 0

    def test_get_or_create_with_company(self):
        store = SessionStore()
        ctx = store.get_or_create(company="Bharat Traders")
        assert ctx.company == "Bharat Traders"

    def test_last_activity_updated_on_add_message(self):
        """Verify last_activity changes after add_message."""
        ctx = SessionContext(session_id="s1")
        initial = ctx.last_activity
        time.sleep(0.01)
        ctx.add_message("user", "hello")
        assert ctx.last_activity > initial

    def test_session_expires_by_last_activity_not_creation(self):
        """A session with old created_at but recent last_activity should NOT expire."""
        store = SessionStore(ttl_minutes=1)  # 60-second TTL
        ctx = store.get_or_create(session_id="s1")
        # Simulate: created long ago, but active recently
        ctx.created_at = time.time() - 600  # 10 minutes ago
        ctx.last_activity = time.time()  # just now
        # Fetching the same session should return it (not expire it)
        retrieved = store.get_or_create(session_id="s1")
        assert retrieved is ctx

    def test_cleanup_expired_removes_stale_sessions(self):
        """cleanup_expired() should remove sessions past their TTL."""
        store = SessionStore(ttl_minutes=1)
        s1 = store.get_or_create(session_id="s1")
        s2 = store.get_or_create(session_id="s2")
        s3 = store.get_or_create(session_id="s3")
        # Make s1 and s2 expired
        s1.last_activity = time.time() - 120
        s2.last_activity = time.time() - 120
        # s3 stays fresh
        store.cleanup_expired()
        assert "s1" not in store._sessions
        assert "s2" not in store._sessions
        assert "s3" in store._sessions

    def test_session_store_uses_config_ttl_by_default(self):
        """Default TTL should match settings.SESSION_TTL_MINUTES."""
        store = SessionStore()
        assert store._ttl_seconds == settings.SESSION_TTL_MINUTES * 60
