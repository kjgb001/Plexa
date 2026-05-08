from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def create_session_factory(
    database_url: str,
    echo: bool = False,
) -> async_sessionmaker[AsyncSession]:
    """Create an async SQLAlchemy session factory.

    Args:
        database_url: SQLAlchemy async database URL.
        echo: Whether SQLAlchemy should echo SQL statements.

    Returns:
        async_sessionmaker[AsyncSession]: Factory for database sessions.
    """
    engine = create_async_engine(database_url, echo=echo, future=True)
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping_database(engine: AsyncEngine) -> bool:
    """Check whether the configured database accepts queries.

    Args:
        engine: Async engine to probe.

    Returns:
        bool: `True` when the database responds to `SELECT 1`.
    """
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
