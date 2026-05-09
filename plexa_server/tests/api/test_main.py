from plexa_server.api import main
from plexa_server.inference.stub import StubInference
from plexa_server.inference.openai_compatible import OpenAICompatibleInference


def test_create_inference_backend_defaults_to_stub(monkeypatch):
    monkeypatch.delenv("PLEXA_INFERENCE_BACKEND", raising=False)

    backend = main.create_inference_backend()

    assert isinstance(backend, StubInference)


def test_create_inference_backend_builds_openai_compatible(monkeypatch):
    monkeypatch.setenv("PLEXA_INFERENCE_BACKEND", "openai-compatible")
    monkeypatch.setenv("PLEXA_OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("PLEXA_OPENAI_DEFAULT_MODEL", "llama3.1")
    monkeypatch.delenv("PLEXA_OPENAI_MODEL_MAP", raising=False)
    monkeypatch.delenv("PLEXA_OPENAI_API_KEY", raising=False)

    backend = main.create_inference_backend()

    assert isinstance(backend, OpenAICompatibleInference)


def test_create_inference_backend_rejects_unknown_backend(monkeypatch):
    monkeypatch.setenv("PLEXA_INFERENCE_BACKEND", "unknown-backend")

    try:
        main.create_inference_backend()
    except ValueError as exc:
        assert "Unsupported inference backend" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown inference backend.")
