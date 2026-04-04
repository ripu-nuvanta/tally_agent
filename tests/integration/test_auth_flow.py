"""Integration tests for auth flow — real Postgres."""
import os
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import User
from backend.utils.auth import hash_password, verify_password

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)

@pytest.mark.asyncio
async def test_create_user_and_verify_password(db_session: AsyncSession):
    user = User(email="test@example.com", password_hash=hash_password("Str0ng!Pass#99"), name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None
    assert user.email == "test@example.com"
    assert verify_password("Str0ng!Pass#99", user.password_hash)
    assert not verify_password("wrong", user.password_hash)

@pytest.mark.asyncio
async def test_email_unique_constraint(db_session: AsyncSession):
    from sqlalchemy.exc import IntegrityError
    user1 = User(email="dupe@example.com", password_hash="hash1", name="User 1")
    db_session.add(user1)
    await db_session.commit()
    user2 = User(email="dupe@example.com", password_hash="hash2", name="User 2")
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()

@pytest.mark.asyncio
async def test_user_lookup_by_email(db_session: AsyncSession):
    user = User(email="lookup@example.com", password_hash="hash", name="Lookup User")
    db_session.add(user)
    await db_session.commit()
    result = await db_session.execute(select(User).where(User.email == "lookup@example.com"))
    found = result.scalar_one_or_none()
    assert found is not None
    assert found.name == "Lookup User"
