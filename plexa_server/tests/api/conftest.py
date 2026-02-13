import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from pydantic import model_validator

from plexa_server.api.app import build_app
from plexa_server.storage.filesystem import FileSystemArtifactStorage
from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload


# Base data directory fixture

@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path


# App fixture

@pytest.fixture
def app(tmp_data_dir: Path):
    return build_app(data_dir=tmp_data_dir)


# Test client fixture

@pytest.fixture
def client(app):
    return TestClient(app)


# Artifact storage fixture

@pytest.fixture
def artifact_storage(tmp_data_dir: Path):
    return FileSystemArtifactStorage(tmp_data_dir)



# Lesson factory

@pytest.fixture
def lesson_factory(artifact_storage):
    def _create():
        lesson = Lesson.model_validate(make_valid_lesson_payload())
        artifact_storage.save_lesson(lesson)
        return lesson

    return _create


# Session factory

@pytest.fixture
def session_factory(client, lesson_factory):
    def _create(lesson_id="test", version="0.1.0", user_id="tester"):
        lesson_factory()

        response = client.post(
            "/sessions",
            json={
                "lesson_id": lesson_id,
                "lesson_version": version,
                "user_id": user_id,
            },
        )

        assert response.status_code == 201
        return response.json()["session"]["session_id"]

    return _create
