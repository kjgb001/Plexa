import asyncio
import os
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from plexa_server.api.app import build_app
from plexa_server.auth.factory import clear_request_authenticator_cache
from plexa_server.core.sessions import SessionManager
from plexa_server.db.config import DatabaseConfig
from plexa_server.db.models import Base
from plexa_server.inference.stub import StubInference
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
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
from plexa_server.utils.cryptography import generate_encryption_key


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def auth_test_mode(monkeypatch):
    """Keep tests on explicit dev-header auth unless overridden locally."""
    monkeypatch.setenv("PLEXA_AUTH_MODE", "dev-header")
    monkeypatch.setenv("PLEXA_ADMIN_USER_IDS", "admin-user")
    clear_request_authenticator_cache()
    yield
    clear_request_authenticator_cache()


@pytest.fixture
def storage_backend() -> str:
    """Return the sole supported application storage backend."""
    return "postgres"


@pytest.fixture
def postgres_test_config() -> DatabaseConfig:
    """Return PostgreSQL test database settings or skip when unavailable."""
    async_url = os.getenv("PLEXA_TEST_DATABASE_URL")
    sync_url = os.getenv("PLEXA_TEST_DATABASE_SYNC_URL")
    if async_url is None and sync_url is None:
        pytest.skip("Postgres tests require PLEXA_TEST_DATABASE_URL or PLEXA_TEST_DATABASE_SYNC_URL.")

    return DatabaseConfig(async_url=async_url, sync_url=sync_url, echo=False)


@pytest.fixture
def postgres_session_factory(postgres_test_config: DatabaseConfig):
    """Create and reset a Postgres test schema for one test run.

    Args:
        postgres_test_config: Postgres test database configuration.

    Returns:
        async_sessionmaker | None: Async SQLAlchemy session factory for Postgres tests.
    """
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
    postgres_session_factory,
) -> dict[str, Any]:
    """Build a coherent set of PostgreSQL storages.

    Args:
        postgres_session_factory: Postgres session factory for Postgres-backed tests.

    Returns:
        dict[str, Any]: Mapping containing artifact, course, and session storages.
    """
    return {
        "artifact": PostgresArtifactStorage(postgres_session_factory),
        "course": PostgresCourseStorage(postgres_session_factory),
        "session": PostgresSessionStorage(postgres_session_factory),
        "workspace": PostgresWorkspaceStateStorage(postgres_session_factory),
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
            "lessons": {},
        })
        run(course_storage.save_course(default_course))
        run(artifact_storage.save_lesson(default_lesson, course_id=default_course.course_id))
        default_course.lessons = {
            default_lesson.identity.lesson_id: default_lesson.identity.version,
        }
        run(course_storage.save_course(default_course))

        backend = inference_backend or StubInference()
        manager = SessionManager(storage=session_storage, inference_backend=backend)
        return manager, session_storage

    return _create


@pytest.fixture
def app(
    artifact_storage,
    session_storage,
    course_storage,
    workspace_state_storage,
    monkeypatch,
) -> FastAPI:
    """Build an application instance for the selected backend.

    Args:
        artifact_storage: Selected artifact storage implementation.
        session_storage: Selected session storage implementation.
        course_storage: Selected course storage implementation.
        workspace_state_storage: Selected workspace-state storage implementation.
        monkeypatch: Pytest environment isolation fixture.

    Returns:
        FastAPI: Configured test application.
    """
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", generate_encryption_key())
    return build_app(
        inference_backend=StubInference(),
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
def lesson_factory():
    """Return a helper that builds a valid lesson for API tests.

    Returns:
        callable: Helper returning a valid `Lesson`.
    """
    def _create():
        from plexa_server.models.lesson import Lesson

        return Lesson.model_validate(make_valid_lesson_payload())

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
        existing_course = client.get(
            f"{api_prefix}/courses/{course_id}",
            headers={"X-User-Id": "admin-user"},
        )
        if existing_course.status_code == 404:
            course_id = course_factory()
        else:
            assert existing_course.status_code == 200

        lesson = lesson_factory()
        lesson.identity.lesson_id = lesson_id
        lesson.identity.version = version
        artifact_path = f"{api_prefix}/courses/{course_id}/lesson-artifacts/{lesson_id}/{version}"
        current = client.get(artifact_path, headers={"X-User-Id": "admin-user"})
        revision_query = ""
        if current.status_code == 200:
            revision_query = f"?expected_revision={current.json()['artifact_revision']}"
        upload = client.post(
            f"{api_prefix}/courses/{course_id}/lesson-artifacts{revision_query}",
            json=lesson.model_dump(mode="json"),
            headers={"X-User-Id": "admin-user"},
        )
        assert upload.status_code == 200
        binding = client.post(
            f"{api_prefix}/courses/{course_id}/lessons",
            json={"lesson_id": lesson_id, "version": version},
            headers={"X-User-Id": "admin-user"},
        )
        assert binding.status_code == 200

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
    """Provide a valid admin identity header for API tests.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        dict: HTTP headers containing a valid admin user identity.
    """
    monkeypatch.setenv("PLEXA_ADMIN_USER_IDS", "admin-user")
    clear_request_authenticator_cache()
    return {"X-User-Id": "admin-user"}


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
