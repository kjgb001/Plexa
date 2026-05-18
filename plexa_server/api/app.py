import json
import os
from pathlib import Path
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from plexa_server.core.sessions import SessionManager
from plexa_server.storage.filesystem import (
    FileSystemSessionStorage,
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
    FileSystemWorkspaceStateStorage,
)
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseStorage,
    SessionStorage,
    WorkspaceStateStorage,
)

from plexa_server.api.routes.sessions import get_sessions_router
from plexa_server.api.routes.health import get_health_router
from plexa_server.api.routes.admin import get_admin_router
from plexa_server.api.routes.courses import get_course_router
from plexa_server.auth.factory import create_request_authenticator
from plexa_server.auth.middleware import create_auth_identity_middleware
from plexa_server.core.encrypted_logs import EncryptedLogService
from plexa_server.inference.base import InferenceBackend
from plexa_server.inference.routing import InferenceRouter, create_single_backend_router
from plexa_server.utils.filesystem_data_dir import get_data_dir_path


DATA_PATH = get_data_dir_path()
APP_VERSION = "0.1.0"
API_VERSION = "v1"


def _load_cors_allowed_origins() -> list[str]:
    """Return configured CORS origins from environment."""
    from plexa_server.db.config import load_server_env_file

    load_server_env_file()
    raw = os.getenv("PLEXA_CORS_ALLOWED_ORIGINS")
    if raw is None or not raw.strip():
        return ["http://localhost:5173"]

    raw = raw.strip()
    if raw.startswith("["):
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise ValueError("PLEXA_CORS_ALLOWED_ORIGINS must be a JSON array of strings or CSV.")
        return [item for item in parsed if item.strip()]

    return [item.strip() for item in raw.split(",") if item.strip()]

def build_app(
    inference_router: InferenceRouter | None = None,
    inference_backend: InferenceBackend | None = None,
    required_backend_ids: set[str] | None = None,
    data_dir: Path | str = DATA_PATH,
    artifact_storage: ArtifactStorage | None = None,
    session_storage: SessionStorage | None = None,
    course_storage: CourseStorage | None = None,
    workspace_state_storage: WorkspaceStateStorage | None = None,
) -> FastAPI:
    """Assemble the FastAPI application and its storage-backed dependencies.

    Args:
        inference_router: Inference router instance to inject into the app.
        inference_backend: Legacy single backend instance for compatibility
            when no router is supplied.
        required_backend_ids: Optional backend ids that must be healthy for
            readiness checks.
        data_dir: Base directory used for filesystem-backed persistence.
        artifact_storage: Optional prebuilt artifact storage implementation.
        session_storage: Optional prebuilt session storage implementation.
        course_storage: Optional prebuilt course storage implementation.

    Returns:
        FastAPI: Configured application instance with all routers mounted.
    """
    data_path = Path(data_dir)

    if inference_router is None:
        if inference_backend is None:
            raise ValueError("build_app requires an inference router or backend.")
        inference_router = create_single_backend_router(inference_backend)

    if (
        artifact_storage is None
        or session_storage is None
        or course_storage is None
        or workspace_state_storage is None
    ):
        from plexa_server.db.config import get_database_config

        database_config = get_database_config()
        use_database = database_config.is_configured and data_path == DATA_PATH
        if use_database:
            from plexa_server.db.session import create_session_factory
            from plexa_server.storage.postgres import (
                PostgresArtifactStorage,
                PostgresCourseStorage,
                PostgresSessionStorage,
                PostgresWorkspaceStateStorage,
            )

            session_factory = create_session_factory(
                database_config.resolved_async_url(),
                echo=database_config.echo,
            )
            artifact_storage = PostgresArtifactStorage(session_factory)
            session_storage = PostgresSessionStorage(session_factory)
            course_storage = PostgresCourseStorage(session_factory)
            workspace_state_storage = PostgresWorkspaceStateStorage(session_factory)
        else:
            artifact_storage = FileSystemArtifactStorage(data_path)
            session_storage = FileSystemSessionStorage(data_path)
            course_storage = FileSystemCourseStorage(data_path)
            workspace_state_storage = FileSystemWorkspaceStateStorage(data_path)

    encrypted_log_service = EncryptedLogService.from_env(artifact_storage, course_storage)
    session_manager = SessionManager(
        storage=session_storage,
        inference_router=inference_router,
        encrypted_log_service=encrypted_log_service,
    )

    # FastAPI app
    app = FastAPI(title="Plexa Server", version=APP_VERSION)
    request_authenticator = create_request_authenticator()
    app.middleware("http")(create_auth_identity_middleware(request_authenticator))
    api_router = APIRouter(prefix=f"/api/{API_VERSION}")

    api_router.include_router(
        get_sessions_router(
            session_manager=session_manager,
            artifact_storage=artifact_storage,
            course_storage=course_storage,
            workspace_state_storage=workspace_state_storage,
        )
    )
    api_router.include_router(
        get_course_router(
            course_storage=course_storage,
            artifact_storage=artifact_storage,
            encrypted_log_service=encrypted_log_service,
            workspace_state_storage=workspace_state_storage,
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
            inference_router=inference_router,
            required_backend_ids=required_backend_ids,
        )
    )
    app.include_router(api_router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_load_cors_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


def get_app(inference_backend):
    """Delegate to `build_app` using the current implementation defaults.

    Args:
        inference_backend: AI inference class object to be used in application instance.
    """
    return build_app(inference_backend=inference_backend)
