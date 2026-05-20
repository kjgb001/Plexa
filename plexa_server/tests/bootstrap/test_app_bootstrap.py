import asyncio
import os

from plexa_server.bootstrap import (
    ensure_bootstrap_environment,
    ensure_env_defaults,
    ensure_log_encryption_key,
    init_dev_database,
    init_test_database,
    write_production_env_template,
)


def test_ensure_env_defaults_generates_file_with_missing_defaults(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.delenv("PLEXA_DATABASE_URL", raising=False)
    monkeypatch.delenv("PLEXA_DATABASE_SYNC_URL", raising=False)
    monkeypatch.delenv("PLEXA_TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("PLEXA_TEST_DATABASE_SYNC_URL", raising=False)
    monkeypatch.delenv("PLEXA_TEST_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_REQUIRED_BACKENDS", raising=False)

    resolved = ensure_env_defaults(env_path)

    assert resolved["PLEXA_DATABASE_URL"].startswith("postgresql+asyncpg://")
    assert resolved["PLEXA_TEST_DATABASE_URL"].endswith("/plexa_test")
    assert resolved["PLEXA_TEST_STORAGE_BACKEND"] == "postgres"
    assert resolved["PLEXA_ENV"] == "development"
    assert resolved["PLEXA_AUTH_MODE"] == "dev-header"
    assert '"ollama-local"' in resolved["PLEXA_INFERENCE_BACKENDS"]
    assert '"vllm-local"' in resolved["PLEXA_INFERENCE_BACKENDS"]
    assert '"default"' in resolved["PLEXA_INFERENCE_PROFILES"]
    assert '"reasoning"' in resolved["PLEXA_INFERENCE_PROFILES"]
    env_text = env_path.read_text(encoding="utf-8")
    assert "PLEXA_DATABASE_URL=" in env_text
    assert "PLEXA_ENV=development" in env_text
    assert "PLEXA_TEST_DATABASE_URL=" in env_text
    assert "PLEXA_INFERENCE_BACKENDS=" in env_text
    assert "PLEXA_INFERENCE_PROFILES=" in env_text


def test_ensure_env_defaults_preserves_existing_values(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("PLEXA_DATABASE_URL=custom-db\n", encoding="utf-8")
    monkeypatch.delenv("PLEXA_DATABASE_URL", raising=False)

    resolved = ensure_env_defaults(env_path)

    assert resolved["PLEXA_DATABASE_URL"] == "custom-db"
    assert "PLEXA_DATABASE_URL=custom-db" in env_path.read_text(encoding="utf-8")


def test_ensure_log_encryption_key_generates_and_persists_when_missing(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.delenv("PLEXA_LOG_ENCRYPTION_KEY", raising=False)

    generated = ensure_log_encryption_key(env_path)

    assert generated
    assert os.environ["PLEXA_LOG_ENCRYPTION_KEY"] == generated
    assert f"PLEXA_LOG_ENCRYPTION_KEY={generated}" in env_path.read_text(encoding="utf-8")


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


def test_ensure_bootstrap_environment_is_additive_and_idempotent(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("PLEXA_DATABASE_URL=custom-db\n", encoding="utf-8")
    monkeypatch.delenv("PLEXA_LOG_ENCRYPTION_KEY", raising=False)

    ensure_bootstrap_environment(env_path)
    first_contents = env_path.read_text(encoding="utf-8")
    ensure_bootstrap_environment(env_path)
    second_contents = env_path.read_text(encoding="utf-8")

    assert "PLEXA_DATABASE_URL=custom-db" in first_contents
    assert "PLEXA_LOG_ENCRYPTION_KEY=" in first_contents
    assert first_contents == second_contents


def test_ensure_bootstrap_environment_rejects_production_without_override(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    monkeypatch.setenv("PLEXA_ENV", "production")
    monkeypatch.delenv("PLEXA_ALLOW_PRODUCTION_BOOTSTRAP", raising=False)

    try:
        ensure_bootstrap_environment(env_path)
    except RuntimeError as exc:
        assert "Refusing to run Plexa bootstrap in production" in str(exc)
    else:
        raise AssertionError("Expected bootstrap to reject production mode by default.")


def test_write_production_env_template_writes_placeholders(tmp_path):
    template_path = tmp_path / ".env.production.example"

    written_path = write_production_env_template(template_path)

    assert written_path == template_path
    template_text = template_path.read_text(encoding="utf-8")
    assert "PLEXA_ENV=production" in template_text
    assert "PLEXA_DATABASE_URL=postgresql+asyncpg://<app_user>:<app_password>@<db_host>:5432/<app_database>" in template_text
    assert "PLEXA_BOOTSTRAP_DATABASE_SYNC_URL=postgresql://<bootstrap_user>:<bootstrap_password>@<db_host>:5432/postgres" in template_text
    assert "PLEXA_LOG_ENCRYPTION_KEY=<generate-and-store-securely>" in template_text


def test_init_dev_database_bootstraps_env_then_db(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    call_order: list[str] = []
    for key in (
        "PLEXA_DATABASE_URL",
        "PLEXA_DATABASE_SYNC_URL",
        "PLEXA_TEST_DATABASE_URL",
        "PLEXA_TEST_DATABASE_SYNC_URL",
        "PLEXA_TEST_STORAGE_BACKEND",
        "PLEXA_INFERENCE_BACKENDS",
        "PLEXA_INFERENCE_PROFILES",
        "PLEXA_INFERENCE_REQUIRED_BACKENDS",
        "PLEXA_LOG_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    async def fake_init_database(config):
        call_order.append("db")

    async def fake_import_filesystem_to_postgres(data_path, target):
        call_order.append(f"import:{target}")

    monkeypatch.setattr("plexa_server.bootstrap.init_database", fake_init_database)
    monkeypatch.setattr(
        "plexa_server.bootstrap.import_filesystem_to_postgres",
        fake_import_filesystem_to_postgres,
    )

    asyncio.run(init_dev_database(import_filesystem=True, env_path=env_path))

    assert call_order == ["db", "import:dev"]
    env_text = env_path.read_text(encoding="utf-8")
    assert "PLEXA_DATABASE_URL=" in env_text
    assert "PLEXA_INFERENCE_BACKENDS=" in env_text
    assert "PLEXA_INFERENCE_PROFILES=" in env_text
    assert "PLEXA_LOG_ENCRYPTION_KEY=" in env_text


def test_init_test_database_bootstraps_env_then_db(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    call_order: list[str] = []
    for key in (
        "PLEXA_DATABASE_URL",
        "PLEXA_DATABASE_SYNC_URL",
        "PLEXA_TEST_DATABASE_URL",
        "PLEXA_TEST_DATABASE_SYNC_URL",
        "PLEXA_TEST_STORAGE_BACKEND",
        "PLEXA_INFERENCE_BACKENDS",
        "PLEXA_INFERENCE_PROFILES",
        "PLEXA_INFERENCE_REQUIRED_BACKENDS",
        "PLEXA_LOG_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    async def fake_init_database(config):
        call_order.append("db")

    async def fake_import_filesystem_to_postgres(data_path, target):
        call_order.append(f"import:{target}")

    monkeypatch.setattr("plexa_server.bootstrap.init_database", fake_init_database)
    monkeypatch.setattr(
        "plexa_server.bootstrap.import_filesystem_to_postgres",
        fake_import_filesystem_to_postgres,
    )

    asyncio.run(init_test_database(import_filesystem=False, env_path=env_path))

    assert call_order == ["db"]
    env_text = env_path.read_text(encoding="utf-8")
    assert "PLEXA_TEST_DATABASE_URL=" in env_text
    assert "PLEXA_INFERENCE_BACKENDS=" in env_text
    assert "PLEXA_INFERENCE_PROFILES=" in env_text
    assert "PLEXA_LOG_ENCRYPTION_KEY=" in env_text
