# --- Database integration test fixtures (Set A1) ---

import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture(scope="session")
def db_available():
    """Skip DB tests if TEST_DATABASE_URL is not set."""
    if not _TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set — skipping DB integration tests")


@pytest_asyncio.fixture
async def db_session(db_available):
    """Create tables, yield a session, then drop tables."""
    from backend.db.models import Base
    engine = create_async_engine(_TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
