"""Tests for session context and session store."""

import time

import pytest

from backend.agents.context import SessionContext, SessionStore


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
        # Force created_at into the past
        ctx1.created_at = time.time() - 1
        ctx2 = store.get_or_create(session_id="expired-session")
        # Should be a new session (no messages)
        assert ctx2.session_id != ctx1.session_id or len(ctx2.messages) == 0

    def test_get_or_create_with_company(self):
        store = SessionStore()
        ctx = store.get_or_create(company="Bharat Traders")
        assert ctx.company == "Bharat Traders"
