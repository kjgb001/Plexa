import uvicorn
from plexa_server.api.app import build_app
from plexa_server.db.config import load_server_env_file
from plexa_server.inference.openai_compatible import OpenAICompatibleInference
from plexa_server.inference.stub import StubInference


def create_inference_backend():
    """Create the configured inference backend from environment settings.

    Returns:
        InferenceBackend: Configured inference backend implementation.

    Raises:
        ValueError: If the configured backend type is unsupported.
    """
    import os

    load_server_env_file()
    backend_name = os.getenv("PLEXA_INFERENCE_BACKEND", "stub").strip().lower()

    if backend_name == "stub":
        return StubInference()
    if backend_name == "openai-compatible":
        return OpenAICompatibleInference.from_env()

    raise ValueError(f"Unsupported inference backend: {backend_name}")


def create_app():
    """Create the default application instance backed by the configured inference backend.

    Returns:
        FastAPI: Application instance configured with the selected backend.
    """
    return build_app(create_inference_backend())


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "plexa_server.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        ws="none"
    )
