import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from plexa_server.api.app import build_app
from plexa_server.core.sessions import SessionManager
from plexa_server.db.config import DatabaseConfig
from plexa_server.db.models import Base
from plexa_server.inference.stub import StubInference
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
    FileSystemSessionStorage,
    FileSystemWorkspaceStateStorage,
)
from plexa_server.storage.postgres import (
    PostgresArtifactStorage,
    PostgresCourseStorage,
    PostgresSessionStorage,
    PostgresWorkspaceStateStorage,
)
from plexa_server.tests.fixtures import (
    make_valid_lesson_payload,
    valid_course,
    valid_lesson,
)


def run(coro):
    return asyncio.run(coro)


def pytest_generate_tests(metafunc):
    """Parametrize storage-backend-aware tests from the CLI option.

    Args:
        metafunc: Pytest metafunc used for dynamic parametrization.
    """
    if "storage_backend" not in metafunc.fixturenames:
        return

    if metafunc.definition.get_closest_marker("postgres_only") is not None:
        metafunc.parametrize("storage_backend", ["postgres"], scope="function")
        return

    option = metafunc.config.getoption("--storage-backend")
    if option is None:
        option = os.getenv("PLEXA_TEST_STORAGE_BACKEND", "filesystem")
    if option == "both":
        params = ["filesystem", "postgres"]
    else:
        params = [option]

    metafunc.parametrize("storage_backend", params, scope="function")


@pytest.fixture
def storage_backend(request) -> str:
    """Return the requested storage backend for the current test.

    Args:
        request: Pytest fixture request object.

    Returns:
        str: Selected backend name.
    """
    if hasattr(request, "param"):
        return request.param

    option = request.config.getoption("--storage-backend")
    if option is None:
        option = os.getenv("PLEXA_TEST_STORAGE_BACKEND", "filesystem")
    if option == "both":
        return "filesystem"
    return option


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Return a temporary filesystem data directory.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path: Temporary data directory path.
    """
    return tmp_path


@pytest.fixture
def postgres_test_config(storage_backend: str) -> DatabaseConfig:
    """Return Postgres test DB settings or skip when unavailable.

    Args:
        storage_backend: Selected storage backend for the test.

    Returns:
        DatabaseConfig: Test database configuration.
    """
    if storage_backend != "postgres":
        return DatabaseConfig()

    async_url = os.getenv("PLEXA_TEST_DATABASE_URL")
    sync_url = os.getenv("PLEXA_TEST_DATABASE_SYNC_URL")
    if async_url is None and sync_url is None:
        pytest.skip("Postgres tests require PLEXA_TEST_DATABASE_URL or PLEXA_TEST_DATABASE_SYNC_URL.")

    return DatabaseConfig(async_url=async_url, sync_url=sync_url, echo=False)


@pytest.fixture
def postgres_session_factory(storage_backend: str, postgres_test_config: DatabaseConfig):
    """Create and reset a Postgres test schema for one test run.

    Args:
        storage_backend: Selected storage backend for the test.
        postgres_test_config: Postgres test database configuration.

    Returns:
        async_sessionmaker | None: Async SQLAlchemy session factory for Postgres tests.
    """
    if storage_backend != "postgres":
        yield None
        return

    engine = create_async_engine(
        postgres_test_config.resolved_async_url(),
        echo=False,
        future=True,
        poolclass=NullPool,
    )

    async def reset_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    run(reset_schema())

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        run(engine.dispose())


@pytest.fixture
def storage_bundle(
    storage_backend: str,
    tmp_data_dir: Path,
    postgres_session_factory,
) -> dict[str, Any]:
    """Build a coherent set of storages for the selected backend.

    Args:
        storage_backend: Selected storage backend for the test.
        tmp_data_dir: Temporary filesystem path for filesystem-backed tests.
        postgres_session_factory: Postgres session factory for Postgres-backed tests.

    Returns:
        dict[str, Any]: Mapping containing artifact, course, and session storages.
    """
    if storage_backend == "postgres":
        return {
            "artifact": PostgresArtifactStorage(postgres_session_factory),
            "course": PostgresCourseStorage(postgres_session_factory),
            "session": PostgresSessionStorage(postgres_session_factory),
            "workspace": PostgresWorkspaceStateStorage(postgres_session_factory),
        }

    return {
        "artifact": FileSystemArtifactStorage(tmp_data_dir),
        "course": FileSystemCourseStorage(tmp_data_dir),
        "session": FileSystemSessionStorage(tmp_data_dir),
        "workspace": FileSystemWorkspaceStateStorage(tmp_data_dir),
    }


@pytest.fixture
def artifact_storage(storage_bundle):
    """Return the artifact storage for the selected backend.

    Args:
        storage_bundle: Mapping of storage instances.

    Returns:
        ArtifactStorage: Selected artifact storage implementation.
    """
    return storage_bundle["artifact"]


@pytest.fixture
def course_storage(storage_bundle):
    """Return the course storage for the selected backend.

    Args:
        storage_bundle: Mapping of storage instances.

    Returns:
        CourseStorage: Selected course storage implementation.
    """
    return storage_bundle["course"]


@pytest.fixture
def session_storage(storage_bundle):
    """Return the session storage for the selected backend.

    Args:
        storage_bundle: Mapping of storage instances.

    Returns:
        SessionStorage: Selected session storage implementation.
    """
    return storage_bundle["session"]


@pytest.fixture
def workspace_state_storage(storage_bundle):
    """Return the workspace-state storage for the selected backend."""
    return storage_bundle["workspace"]


@pytest.fixture
def setup_manager(session_storage, artifact_storage, course_storage):
    """Return a helper that builds a session manager for the active backend.

    Args:
        session_storage: Selected session storage implementation.
        artifact_storage: Selected artifact storage implementation.
        course_storage: Selected course storage implementation.

    Returns:
        callable: Helper returning `(SessionManager, session_storage)`.
    """
    def _create(inference_backend=None):
        default_lesson = Lesson.model_validate(make_valid_lesson_payload())
        default_course = Course.model_validate({
            "course_id": "CS101",
            "title": "Intro to AI",
            "description": "Session manager backend test course",
            "owner_id": "test-owner",
            "instructor_ids": ["test-owner"],
            "enrolled_users": ["user-1"],
            "discoverable": True,
            "lessons": {
                default_lesson.identity.lesson_id: default_lesson.identity.version,
            },
        })
        run(artifact_storage.save_lesson(default_lesson))
        run(course_storage.save_course(default_course))

        backend = inference_backend or StubInference()
        manager = SessionManager(storage=session_storage, inference_backend=backend)
        return manager, session_storage

    return _create


@pytest.fixture
def app(
    tmp_data_dir: Path,
    artifact_storage,
    session_storage,
    course_storage,
    workspace_state_storage,
) -> FastAPI:
    """Build an application instance for the selected backend.

    Args:
        tmp_data_dir: Temporary filesystem path used when relevant.
        artifact_storage: Selected artifact storage implementation.
        session_storage: Selected session storage implementation.
        course_storage: Selected course storage implementation.

    Returns:
        FastAPI: Configured test application.
    """
    return build_app(
        inference_backend=StubInference(),
        data_dir=tmp_data_dir,
        artifact_storage=artifact_storage,
        session_storage=session_storage,
        course_storage=course_storage,
        workspace_state_storage=workspace_state_storage,
    )


@pytest.fixture
def client(app) -> TestClient:
    """Create a synchronous FastAPI test client.

    Args:
        app: Configured FastAPI application.

    Returns:
        TestClient: Synchronous API test client.
    """
    return TestClient(app)


@pytest.fixture
def lesson_factory(artifact_storage):
    """Return a helper that persists a valid lesson for the current backend.

    Args:
        artifact_storage: Selected artifact storage implementation.

    Returns:
        callable: Helper returning the persisted `Lesson`.
    """
    def _create():
        from plexa_server.models.lesson import Lesson

        lesson = Lesson.model_validate(make_valid_lesson_payload())
        run(artifact_storage.save_lesson(lesson))
        return lesson

    return _create


@pytest.fixture
def session_factory(client, lesson_factory, course_factory, api_prefix):
    """Return a helper that creates a session through the API.

    Args:
        client: API test client.
        lesson_factory: Helper that seeds a lesson.
        course_factory: Helper that seeds a course.
        api_prefix: Versioned API prefix.

    Returns:
        callable: Helper returning `(session_id, lesson_id, lesson_version)`.
    """
    def _create(lesson_id="test", version="0.1.0", user_id="tester", course_id="CS101"):
        lesson_factory()
        try:
            course_id = course_factory()
        except Exception:
            pass

        response = client.post(
            f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{version}/sessions",
            headers={"X-User-Id": user_id},
        )

        assert response.status_code == 201
        return response.json()["session"]["session_id"], lesson_id, version

    return _create


@pytest.fixture
def course_factory(client, valid_course_payload, admin_headers, api_prefix):
    """Return a helper that creates a course through the admin API.

    Args:
        client: API test client.
        valid_course_payload: Valid course payload fixture.
        admin_headers: Admin auth headers.
        api_prefix: Versioned API prefix.

    Returns:
        callable: Helper returning the created course id.
    """
    def _create():
        payload = valid_course_payload
        response = client.post(
            f"{api_prefix}/admin/courses",
            json=payload,
            headers=admin_headers,
        )

        assert response.status_code == 200
        return response.json()["course_id"]

    return _create


@pytest.fixture
def admin_headers(monkeypatch) -> dict:
    """Provide a valid admin header for API tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        dict: HTTP headers containing a valid admin token.
    """
    monkeypatch.setenv("PLEXA_ADMIN_TOKEN", "test-token")
    return {"X-Admin-Token": "test-token"}


@pytest.fixture
def valid_lesson_payload() -> dict:
    """Return a valid lesson payload fixture.

    Returns:
        dict: Valid lesson payload.
    """
    return valid_lesson()


@pytest.fixture
def valid_course_payload() -> dict:
    """Return a valid course payload fixture.

    Returns:
        dict: Valid course payload.
    """
    return valid_course()


@pytest.fixture
def api_prefix() -> str:
    """Return the versioned API prefix used in tests.

    Returns:
        str: API prefix.
    """
    return "/api/v1"
