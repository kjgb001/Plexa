import os
from pathlib import Path

import uvicorn
from plexa_server.api.app import build_app
from plexa_server.inference.stub import StubInference


def create_app():
    """Create the default application instance backed by the stub inference backend.

    Returns:
        FastAPI: Application instance configured with `StubInference`.
    """
    #data_dir = Path(os.environ.get("PLEXA_DATA_DIR", "data"))
    return build_app(StubInference())


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "plexa_server.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        ws="none"
    )
