import os

from plexa_server.db.bootstrap import ensure_log_encryption_key, init_database
from plexa_server.db.config import DatabaseConfig


def test_ensure_log_encryption_key_generates_and_persists_when_missing(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.delenv("PLEXA_LOG_ENCRYPTION_KEY", raising=False)

    generated = ensure_log_encryption_key(env_path)

    assert generated
    assert os.environ["PLEXA_LOG_ENCRYPTION_KEY"] == generated
    file_text = env_path.read_text(encoding="utf-8")
    assert f"PLEXA_LOG_ENCRYPTION_KEY={generated}" in file_text


def test_ensure_log_encryption_key_preserves_existing_file_value(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("PLEXA_LOG_ENCRYPTION_KEY=existing-key\nOTHER=value\n", encoding="utf-8")
    monkeypatch.delenv("PLEXA_LOG_ENCRYPTION_KEY", raising=False)

    resolved = ensure_log_encryption_key(env_path)

    assert resolved == "existing-key"
    assert os.environ["PLEXA_LOG_ENCRYPTION_KEY"] == "existing-key"
    assert env_path.read_text(encoding="utf-8") == "PLEXA_LOG_ENCRYPTION_KEY=existing-key\nOTHER=value\n"


def test_ensure_log_encryption_key_prefers_process_environment(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("PLEXA_LOG_ENCRYPTION_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", "process-key")

    resolved = ensure_log_encryption_key(env_path)

    assert resolved == "process-key"
    assert env_path.read_text(encoding="utf-8") == "PLEXA_LOG_ENCRYPTION_KEY=file-key\n"


def test_init_database_bootstrap_generates_key_before_db_steps(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.delenv("PLEXA_LOG_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr("plexa_server.db.bootstrap.SERVER_ENV_PATH", env_path)

    call_order: list[str] = []

    async def fake_wait_for_postgres(config):
        call_order.append("wait")

    async def fake_ensure_database_exists(config):
        call_order.append("ensure_db")

    async def fake_run_migrations(config):
        call_order.append("migrate")

    monkeypatch.setattr("plexa_server.db.bootstrap.wait_for_postgres", fake_wait_for_postgres)
    monkeypatch.setattr("plexa_server.db.bootstrap.ensure_database_exists", fake_ensure_database_exists)
    monkeypatch.setattr("plexa_server.db.bootstrap.run_migrations", fake_run_migrations)

    config = DatabaseConfig(
        async_url="postgresql+asyncpg://plexa:pw@localhost:5432/plexa",
        sync_url="postgresql://plexa:pw@localhost:5432/plexa",
    )

    import asyncio

    asyncio.run(init_database(config))

    assert call_order == ["wait", "ensure_db", "migrate"]
    generated = os.environ["PLEXA_LOG_ENCRYPTION_KEY"]
    assert generated
    assert f"PLEXA_LOG_ENCRYPTION_KEY={generated}" in env_path.read_text(encoding="utf-8")


def test_init_database_does_not_rotate_existing_key(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("PLEXA_LOG_ENCRYPTION_KEY=stable-key\n", encoding="utf-8")
    monkeypatch.delenv("PLEXA_LOG_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr("plexa_server.db.bootstrap.SERVER_ENV_PATH", env_path)

    async def fake_wait_for_postgres(config):
        return None

    async def fake_ensure_database_exists(config):
        return None

    async def fake_run_migrations(config):
        return None

    monkeypatch.setattr("plexa_server.db.bootstrap.wait_for_postgres", fake_wait_for_postgres)
    monkeypatch.setattr("plexa_server.db.bootstrap.ensure_database_exists", fake_ensure_database_exists)
    monkeypatch.setattr("plexa_server.db.bootstrap.run_migrations", fake_run_migrations)

    config = DatabaseConfig(
        async_url="postgresql+asyncpg://plexa:pw@localhost:5432/plexa",
        sync_url="postgresql://plexa:pw@localhost:5432/plexa",
    )

    import asyncio

    asyncio.run(init_database(config))

    assert os.environ["PLEXA_LOG_ENCRYPTION_KEY"] == "stable-key"
    assert env_path.read_text(encoding="utf-8") == "PLEXA_LOG_ENCRYPTION_KEY=stable-key\n"
