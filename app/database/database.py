"""
SQLAlchemy async engine and session factory.

Usage in routers:
    from app.database.database import get_db
    ...
    async def endpoint(db: AsyncSession = Depends(get_db)):
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Replace postgresql:// with postgresql+asyncpg:// for async driver
_DATABASE_URL = settings.database_url
if _DATABASE_URL.startswith("postgresql://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    _DATABASE_URL or "postgresql+asyncpg://user:password@localhost:5432/tg_bot_finans",
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
