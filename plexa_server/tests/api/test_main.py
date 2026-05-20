from plexa_server.api import main
from plexa_server.db import config as db_config
from plexa_server.inference.base import InferenceConfig
from plexa_server.inference.routing import InferenceRouter
from plexa_server.inference.stub import StubInference
from plexa_server.inference.openai_compatible import OpenAICompatibleInference
from plexa_server import runtime
from plexa_server.runtime import RuntimeConfigurationError


def _disable_env_file_loading(monkeypatch):
    """Keep tests focused on explicit env mutations, not ambient `.env` state."""
    monkeypatch.setattr(main, "load_server_env_file", lambda: None)
    monkeypatch.setattr(runtime, "load_server_env_file", lambda: None)
    monkeypatch.setattr(db_config, "_load_env_file", lambda: None)


def test_create_inference_registry_defaults_to_stub(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKEND", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    registry = main.create_inference_registry()

    assert isinstance(registry.get_backend("stub"), StubInference)


def test_create_inference_registry_builds_openai_compatible(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_INFERENCE_BACKEND", "openai-compatible")
    monkeypatch.setenv("PLEXA_OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("PLEXA_OPENAI_DEFAULT_MODEL", "llama3.1")
    monkeypatch.delenv("PLEXA_OPENAI_MODEL_MAP", raising=False)
    monkeypatch.delenv("PLEXA_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    registry = main.create_inference_registry()

    assert isinstance(registry.get_backend("openai-compatible"), OpenAICompatibleInference)
    assert registry.get_profile("default").model == "llama3.1"


def test_create_inference_router_defaults_to_stub_fallback(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKEND", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    router = main.create_inference_router()

    assert isinstance(router, InferenceRouter)
    assert router.resolve(InferenceConfig(profile="anything")).backend_id == "stub"


def test_create_inference_registry_builds_multiple_backends(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv(
        "PLEXA_INFERENCE_BACKENDS",
        '{"stub-a":{"type":"stub"},"stub-b":{"type":"stub"}}',
    )
    monkeypatch.setenv(
        "PLEXA_INFERENCE_PROFILES",
        '{"default":{"backend_id":"stub-a","model":"model-a"},"fast":{"backend_id":"stub-b","model":"model-b"}}',
    )

    registry = main.create_inference_registry()

    assert isinstance(registry.get_backend("stub-a"), StubInference)
    assert registry.get_profile("fast").backend_id == "stub-b"


def test_create_required_backend_ids_from_json(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_INFERENCE_REQUIRED_BACKENDS", '["stub-a","stub-b"]')
    monkeypatch.delenv("PLEXA_INFERENCE_REQUIRED_BACKENDS_CSV", raising=False)

    assert main.create_required_backend_ids() == {"stub-a", "stub-b"}


def test_create_inference_registry_rejects_unknown_backend(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_INFERENCE_BACKEND", "unknown-backend")
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    try:
        main.create_inference_registry()
    except ValueError as exc:
        assert "Unsupported inference backend" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown inference backend.")


def test_create_app_rejects_production_dev_auth(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_ENV", "production")
    monkeypatch.setenv("PLEXA_DATABASE_URL", "postgresql+asyncpg://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_DATABASE_SYNC_URL", "postgresql://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_AUTH_MODE", "dev-header")
    monkeypatch.setenv("PLEXA_CORS_ALLOWED_ORIGINS", '["https://client.example"]')
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", "test-key")

    try:
        main.create_app()
    except RuntimeConfigurationError as exc:
        assert "cannot use PLEXA_AUTH_MODE=dev-header" in str(exc)
    else:
        raise AssertionError("Expected production startup to reject dev-header auth mode.")


def test_create_app_rejects_missing_production_log_key(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_ENV", "production")
    monkeypatch.setenv("PLEXA_DATABASE_URL", "postgresql+asyncpg://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_DATABASE_SYNC_URL", "postgresql://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_AUTH_MODE", "bearer-jwt")
    monkeypatch.setenv("PLEXA_AUTH_SHARED_SECRET", "secret")
    monkeypatch.setenv("PLEXA_AUTH_ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("PLEXA_CORS_ALLOWED_ORIGINS", '["https://client.example"]')
    monkeypatch.setenv(
        "PLEXA_INFERENCE_BACKENDS",
        '{"real-a":{"type":"openai-compatible","base_url":"http://inference/v1"}}',
    )
    monkeypatch.setenv(
        "PLEXA_INFERENCE_PROFILES",
        '{"default":{"backend_id":"real-a","model":"model-a"}}',
    )
    monkeypatch.delenv("PLEXA_LOG_ENCRYPTION_KEY", raising=False)

    try:
        main.create_app()
    except RuntimeConfigurationError as exc:
        assert "PLEXA_LOG_ENCRYPTION_KEY" in str(exc)
    else:
        raise AssertionError("Expected production startup to require encrypted log key.")


def test_create_app_rejects_production_stub_inference_fallback(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_ENV", "production")
    monkeypatch.setenv("PLEXA_DATABASE_URL", "postgresql+asyncpg://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_DATABASE_SYNC_URL", "postgresql://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_AUTH_MODE", "bearer-jwt")
    monkeypatch.setenv("PLEXA_AUTH_SHARED_SECRET", "secret")
    monkeypatch.setenv("PLEXA_AUTH_ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("PLEXA_CORS_ALLOWED_ORIGINS", '["https://client.example"]')
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", "test-key")
    monkeypatch.delenv("PLEXA_INFERENCE_BACKEND", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    try:
        main.create_app()
    except RuntimeConfigurationError as exc:
        assert "cannot fall back to stub" in str(exc)
    else:
        raise AssertionError("Expected production startup to reject stub inference fallback.")


def test_create_app_rejects_production_stub_backend_in_multi_backend_config(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_ENV", "production")
    monkeypatch.setenv("PLEXA_DATABASE_URL", "postgresql+asyncpg://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_DATABASE_SYNC_URL", "postgresql://plexa:pw@db/plexa")
    monkeypatch.setenv("PLEXA_AUTH_MODE", "bearer-jwt")
    monkeypatch.setenv("PLEXA_AUTH_SHARED_SECRET", "secret")
    monkeypatch.setenv("PLEXA_AUTH_ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("PLEXA_CORS_ALLOWED_ORIGINS", '["https://client.example"]')
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", "test-key")
    monkeypatch.setenv(
        "PLEXA_INFERENCE_BACKENDS",
        '{"stub-a":{"type":"stub"},"real-a":{"type":"openai-compatible","base_url":"http://inference/v1"}}',
    )
    monkeypatch.setenv(
        "PLEXA_INFERENCE_PROFILES",
        '{"default":{"backend_id":"real-a","model":"model-a"}}',
    )

    try:
        main.create_app()
    except RuntimeConfigurationError as exc:
        assert "cannot use stub inference backends" in str(exc)
    else:
        raise AssertionError("Expected production startup to reject stub backend definitions.")


def test_create_app_rejects_production_dev_database_password(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_ENV", "production")
    monkeypatch.setenv(
        "PLEXA_DATABASE_URL",
        "postgresql+asyncpg://plexa:plexa_dev_password@db/plexa",
    )
    monkeypatch.setenv(
        "PLEXA_DATABASE_SYNC_URL",
        "postgresql://plexa:plexa_dev_password@db/plexa",
    )
    monkeypatch.setenv("PLEXA_AUTH_MODE", "bearer-jwt")
    monkeypatch.setenv("PLEXA_AUTH_SHARED_SECRET", "secret")
    monkeypatch.setenv("PLEXA_AUTH_ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("PLEXA_CORS_ALLOWED_ORIGINS", '["https://client.example"]')
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", "test-key")
    monkeypatch.setenv(
        "PLEXA_INFERENCE_BACKENDS",
        '{"real-a":{"type":"openai-compatible","base_url":"http://inference/v1"}}',
    )
    monkeypatch.setenv(
        "PLEXA_INFERENCE_PROFILES",
        '{"default":{"backend_id":"real-a","model":"model-a"}}',
    )

    try:
        main.create_app()
    except RuntimeConfigurationError as exc:
        assert "development-only database value" in str(exc)
    else:
        raise AssertionError("Expected production startup to reject dev database password.")


def test_create_app_rejects_production_test_database_name(monkeypatch):
    _disable_env_file_loading(monkeypatch)
    monkeypatch.setenv("PLEXA_ENV", "production")
    monkeypatch.setenv(
        "PLEXA_DATABASE_URL",
        "postgresql+asyncpg://plexa:secure-password@db/plexa_test",
    )
    monkeypatch.setenv(
        "PLEXA_DATABASE_SYNC_URL",
        "postgresql://plexa:secure-password@db/plexa_test",
    )
    monkeypatch.setenv("PLEXA_AUTH_MODE", "bearer-jwt")
    monkeypatch.setenv("PLEXA_AUTH_SHARED_SECRET", "secret")
    monkeypatch.setenv("PLEXA_AUTH_ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("PLEXA_CORS_ALLOWED_ORIGINS", '["https://client.example"]')
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", "test-key")
    monkeypatch.setenv(
        "PLEXA_INFERENCE_BACKENDS",
        '{"real-a":{"type":"openai-compatible","base_url":"http://inference/v1"}}',
    )
    monkeypatch.setenv(
        "PLEXA_INFERENCE_PROFILES",
        '{"default":{"backend_id":"real-a","model":"model-a"}}',
    )

    try:
        main.create_app()
    except RuntimeConfigurationError as exc:
        assert "development-only database value" in str(exc)
    else:
        raise AssertionError("Expected production startup to reject test database name.")
