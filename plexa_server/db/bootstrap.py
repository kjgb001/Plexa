import asyncio

import asyncpg
from alembic import command
from alembic.config import Config

from plexa_server.db.config import (
    DatabaseConfig,
    get_bootstrap_database_config,
)
from pathlib import Path


ALEMBIC_INI_PATH = Path(__file__).resolve().parent.parent / "alembic.ini"


def _postgres_dsn(async_url: str) -> str:
    """Convert a SQLAlchemy asyncpg URL into an asyncpg DSN.

    Args:
        async_url: SQLAlchemy async database URL.

    Returns:
        str: DSN string accepted by `asyncpg.connect`.
    """
    return async_url.replace("postgresql+asyncpg://", "postgres://", 1)


def _quote_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier safely.

    Args:
        identifier: Identifier to quote.

    Returns:
        str: Double-quoted SQL identifier.
    """
    return '"' + identifier.replace('"', '""') + '"'


async def wait_for_postgres(
    config: DatabaseConfig,
    attempts: int = 20,
    delay_s: float = 1.0,
) -> None:
    """Wait until PostgreSQL accepts connections.

    Args:
        config: Database configuration to probe.
        attempts: Maximum connection attempts before failing.
        delay_s: Delay between attempts in seconds.

    Raises:
        RuntimeError: If PostgreSQL never becomes reachable.
    """
    last_error = None
    dsn = _postgres_dsn(config.resolved_async_url())
    for _ in range(attempts):
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            return
        except Exception as exc:  # pragma: no cover - runtime infra dependent
            last_error = exc
            await asyncio.sleep(delay_s)

    raise RuntimeError(f"PostgreSQL did not become reachable: {last_error}")


async def ensure_database_exists(target: DatabaseConfig) -> None:
    """Create a target database if it does not already exist.

    Args:
        target: Target database configuration.
    """
    bootstrap = get_bootstrap_database_config(target)
    conn = await asyncpg.connect(_postgres_dsn(bootstrap.resolved_async_url()))
    try:
        db_name = target.database_name()
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name,
        )
        if exists:
            return

        await conn.execute(f"CREATE DATABASE {_quote_identifier(db_name)}")
    finally:
        await conn.close()


def _run_migrations_sync(target: DatabaseConfig) -> None:
    """Apply Alembic migrations to the target database synchronously.

    Args:
        target: Target database configuration.
    """
    alembic_config = Config(str(ALEMBIC_INI_PATH))
    alembic_config.set_main_option("sqlalchemy.url", target.resolved_async_url())
    command.upgrade(alembic_config, "head")


async def run_migrations(target: DatabaseConfig) -> None:
    """Apply Alembic migrations to the target database from async code.

    Args:
        target: Target database configuration.
    """
    await asyncio.to_thread(_run_migrations_sync, target)


async def init_database(target: DatabaseConfig) -> None:
    """Ensure a database exists and migrate it to the latest schema.

    Args:
        target: Target database configuration.
    """
    if not target.is_configured:
        raise ValueError("Target database configuration is missing.")

    await wait_for_postgres(get_bootstrap_database_config(target))
    await ensure_database_exists(target)
    await run_migrations(target)
