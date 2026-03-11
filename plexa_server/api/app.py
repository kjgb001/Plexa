import os
from pathlib import Path
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from plexa_server.core.sessions import SessionManager
from plexa_server.storage.filesystem import (
    FileSystemSessionStorage,
    FileSystemArtifactStorage,
    FileSystemCourseStorage
)

from plexa_server.api.routes.sessions import get_sessions_router
from plexa_server.api.routes.health import get_health_router
from plexa_server.api.routes.admin import get_admin_router
from plexa_server.api.routes.courses import get_course_router
from plexa_server.utils.filesystem_data_dir import get_data_dir_path


DATA_PATH = get_data_dir_path()
APP_VERSION = "0.1.0"
API_VERSION = "v1"

def build_app(
    inference_backend,
    data_dir: Path | str = DATA_PATH,
) -> FastAPI:
    data_path = Path(data_dir)

    # Infrastructure wiring (composition root)
    artifact_storage = FileSystemArtifactStorage(data_path)
    session_storage = FileSystemSessionStorage(data_path)
    course_storage = FileSystemCourseStorage(data_path)
    inference_backend = inference_backend

    session_manager = SessionManager(
        storage=session_storage,
        inference_backend=inference_backend,
    )

    # FastAPI app
    app = FastAPI(title="Plexa Server", version=APP_VERSION)
    api_router = APIRouter(prefix=f"/api/{API_VERSION}")

    api_router.include_router(
        get_sessions_router(
            session_manager=session_manager,
            artifact_storage=artifact_storage,
            course_storage=course_storage
        )
    )
    api_router.include_router(
        get_course_router(
            course_storage=course_storage,
            artifact_storage=artifact_storage
        )
    )
    api_router.include_router(
        get_admin_router(
            artifact_storage=artifact_storage,
            course_storage=course_storage
        )
    )
    app.include_router(
        get_health_router(
            session_storage=session_storage,
            artifact_storage=artifact_storage,
            inference_backend=inference_backend,
        )
    )
    app.include_router(api_router)

    # DEV: Allow cross-origin requests from port 5173 (client dev)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


def get_app():
    return build_app()