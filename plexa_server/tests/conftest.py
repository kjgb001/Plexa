import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from pydantic import model_validator

from plexa_server.api.app import build_app
from plexa_server.storage.filesystem import FileSystemArtifactStorage
from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload
from plexa_server.inference.stub import StubInference

from plexa_server.tests.fixtures import (
    valid_course,
    valid_lesson
)


# Base data directory fixture

@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path


# App fixture

@pytest.fixture
def app(tmp_data_dir: Path) -> FastAPI:
    return build_app(
        inference_backend=StubInference(), 
        data_dir=tmp_data_dir
    )


# Test client fixture

@pytest.fixture
def client(app) -> client:
    return TestClient(app)


# Artifact storage fixture

@pytest.fixture
def artifact_storage(tmp_data_dir: Path) -> FileSystemArtifactStorage:
    return FileSystemArtifactStorage(tmp_data_dir)



# Lesson factory

@pytest.fixture
def lesson_factory(artifact_storage) -> Lesson:
    def _create():
        lesson = Lesson.model_validate(make_valid_lesson_payload())
        artifact_storage.save_lesson(lesson)
        return lesson

    return _create


# Session factory

@pytest.fixture
def session_factory(client, lesson_factory, course_factory, api_prefix) -> String:
    def _create(lesson_id="test", version="0.1.0", user_id="tester", course_id="CS101"):
        lesson_factory()
        course_id = course_factory()

        response = client.post(
            f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{version}/sessions",
            headers={"X-User-Id": user_id}
        )

        assert response.status_code == 201
        return response.json()["session"]["session_id"], lesson_id, version

    return _create


@pytest.fixture
def course_factory(client, valid_course_payload, admin_headers, api_prefix) -> String:
    def _create():
        payload = valid_course_payload
        headers = admin_headers

        response = client.post(
            f"{api_prefix}/admin/courses",
            json=payload,
            headers=headers
        )

        assert response.status_code == 200
        return response.json()["course_id"]

    return _create


# Admin token environment var

@pytest.fixture
def admin_headers(monkeypatch) -> dict:
    monkeypatch.setenv("PLEXA_ADMIN_TOKEN", "test-token")
    return {"X-Admin-Token": "test-token"}


@pytest.fixture
def valid_lesson_payload() -> Lesson:
    return valid_lesson()


@pytest.fixture
def valid_course_payload() -> Course:
    return valid_course()


@pytest.fixture
def api_prefix() -> str:
    return (f"/api/v1")
