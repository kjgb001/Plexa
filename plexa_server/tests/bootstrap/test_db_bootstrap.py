import asyncio

from plexa_server.db.bootstrap import init_database
from plexa_server.db.config import DatabaseConfig


def test_init_database_runs_db_steps_in_order(monkeypatch):
    call_order: list[str] = []

    async def fake_wait_for_postgres(config):
        call_order.append("wait")

    async def fake_ensure_database_exists(config):
        call_order.append("ensure_db")

    async def fake_run_migrations(config):
        call_order.append("migrate")

    async def fake_reset_database_schema(config):
        call_order.append("reset")

    monkeypatch.setattr("plexa_server.db.bootstrap.wait_for_postgres", fake_wait_for_postgres)
    monkeypatch.setattr("plexa_server.db.bootstrap.ensure_database_exists", fake_ensure_database_exists)
    monkeypatch.setattr("plexa_server.db.bootstrap.run_migrations", fake_run_migrations)
    monkeypatch.setattr("plexa_server.db.bootstrap.reset_database_schema", fake_reset_database_schema)

    config = DatabaseConfig(
        async_url="postgresql+asyncpg://plexa:pw@localhost:5432/plexa",
        sync_url="postgresql://plexa:pw@localhost:5432/plexa",
    )

    asyncio.run(init_database(config))

    assert call_order == ["wait", "ensure_db", "migrate"]


def test_init_database_can_reset_schema_before_migrations(monkeypatch):
    call_order: list[str] = []

    async def fake_wait_for_postgres(config):
        call_order.append("wait")

    async def fake_ensure_database_exists(config):
        call_order.append("ensure_db")

    async def fake_reset_database_schema(config):
        call_order.append("reset")

    async def fake_run_migrations(config):
        call_order.append("migrate")

    monkeypatch.setattr("plexa_server.db.bootstrap.wait_for_postgres", fake_wait_for_postgres)
    monkeypatch.setattr("plexa_server.db.bootstrap.ensure_database_exists", fake_ensure_database_exists)
    monkeypatch.setattr("plexa_server.db.bootstrap.reset_database_schema", fake_reset_database_schema)
    monkeypatch.setattr("plexa_server.db.bootstrap.run_migrations", fake_run_migrations)

    config = DatabaseConfig(
        async_url="postgresql+asyncpg://plexa:pw@localhost:5432/plexa_test",
        sync_url="postgresql://plexa:pw@localhost:5432/plexa_test",
    )

    asyncio.run(init_database(config, reset_schema=True))

    assert call_order == ["wait", "ensure_db", "reset", "migrate"]


def test_init_database_requires_config():
    try:
        asyncio.run(init_database(DatabaseConfig()))
    except ValueError as exc:
        assert "Target database configuration is missing." in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing database configuration.")
