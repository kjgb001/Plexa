import os
from pathlib import Path
from fastapi import FastAPI

from plexa_server.core.sessions import SessionManager
from plexa_server.storage.filesystem import FileSystemSessionStorage
from plexa_server.storage.filesystem import FileSystemArtifactStorage
from plexa_server.inference.stub import StubInference

from plexa_server.api.routes.sessions import get_sessions_router


DATA_PATH = Path(os.path.join(os.path.dirname(__file__), "../data"))

def build_app(data_dir: Path | str = DATA_PATH) -> FastAPI:
    data_path = Path(data_dir)

    # Infrastructure wiring (composition root)
    artifact_storage = FileSystemArtifactStorage(data_path)
    session_storage = FileSystemSessionStorage(data_path)
    inference_backend = StubInference()

    session_manager = SessionManager(
        storage=session_storage,
        inference_backend=inference_backend,
    )

    # FastAPI app
    app = FastAPI(title="Plexa Server", version="0.1.0")

    app.include_router(
        get_sessions_router(
            session_manager=session_manager,
            artifact_storage=artifact_storage,
        )
    )

    return app


def get_app():
    return build_app()