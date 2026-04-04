"""Async SQLAlchemy engine and session factory."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from backend.config import settings

engine = None
async_session_factory = None

def init_engine(database_url: str | None = None) -> None:
    global engine, async_session_factory
    url = database_url or settings.DATABASE_URL
    if not url:
        raise ValueError("DATABASE_URL must be set to initialize the database engine")
    engine = create_async_engine(url, echo=False, pool_size=5, max_overflow=10)
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Set DATABASE_URL to enable DB mode.")
    async with async_session_factory() as session:
        yield session

async def close_engine() -> None:
    global engine, async_session_factory
    if engine:
        await engine.dispose()
    engine = None
    async_session_factory = None
