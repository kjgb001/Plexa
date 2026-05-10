from plexa_server.api import main
from plexa_server.inference.base import InferenceConfig
from plexa_server.inference.routing import InferenceRouter
from plexa_server.inference.stub import StubInference
from plexa_server.inference.openai_compatible import OpenAICompatibleInference


def test_create_inference_registry_defaults_to_stub(monkeypatch):
    monkeypatch.delenv("PLEXA_INFERENCE_BACKEND", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    registry = main.create_inference_registry()

    assert isinstance(registry.get_backend("stub"), StubInference)


def test_create_inference_registry_builds_openai_compatible(monkeypatch):
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
    monkeypatch.delenv("PLEXA_INFERENCE_BACKEND", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    router = main.create_inference_router()

    assert isinstance(router, InferenceRouter)
    assert router.resolve(InferenceConfig(profile="anything")).backend_id == "stub"


def test_create_inference_registry_builds_multiple_backends(monkeypatch):
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
    monkeypatch.setenv("PLEXA_INFERENCE_REQUIRED_BACKENDS", '["stub-a","stub-b"]')
    monkeypatch.delenv("PLEXA_INFERENCE_REQUIRED_BACKENDS_CSV", raising=False)

    assert main.create_required_backend_ids() == {"stub-a", "stub-b"}


def test_create_inference_registry_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("PLEXA_INFERENCE_BACKEND", "unknown-backend")
    monkeypatch.delenv("PLEXA_INFERENCE_BACKENDS", raising=False)
    monkeypatch.delenv("PLEXA_INFERENCE_PROFILES", raising=False)

    try:
        main.create_inference_registry()
    except ValueError as exc:
        assert "Unsupported inference backend" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown inference backend.")
