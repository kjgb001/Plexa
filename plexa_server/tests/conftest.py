import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from pydantic import model_validator

from plexa_server.api.app import build_app
from plexa_server.storage.filesystem import FileSystemArtifactStorage
from plexa_server.models.lesson import Lesson
from plexa_server.tests.fixtures import make_valid_lesson_payload
from plexa_server.inference.stub import StubInference


# Base data directory fixture

@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path


# App fixture

@pytest.fixture
def app(tmp_data_dir: Path):
    return build_app(
        inference_backend=StubInference(), 
        data_dir=tmp_data_dir
    )


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
def session_factory(client, lesson_factory, course_factory):
    def _create(lesson_id="test", version="0.1.0", user_id="tester", course_id="CS101"):
        lesson_factory()
        course_factory()

        response = client.post(
            "/sessions",
            json={
                "lesson_id": lesson_id,
                "course_id": course_id,
                "lesson_version": version,
            },
            headers={"X-User-Id": user_id, "X-Course-Id": course_id}
        )

        assert response.status_code == 201
        return response.json()["session"]["session_id"]

    return _create


@pytest.fixture
def course_factory(client, valid_course_payload, admin_headers):
    def _create():
        payload = valid_course_payload
        headers = admin_headers

        response = client.post(
            "/admin/courses",
            json=payload,
            headers=headers
        )

        assert response.status_code == 200
        return response.json()["course_id"]

    return _create

# Admin token environment var

@pytest.fixture
def admin_headers(monkeypatch):
    monkeypatch.setenv("PLEXA_ADMIN_TOKEN", "test-token")
    return {"X-Admin-Token": "test-token"}


@pytest.fixture
def valid_lesson_payload() -> Lesson:
    return {
        "identity": {
            "lesson_id": "test",
            "version": "0.1.0",
            "title": "Introduction to LLM Behavior",
            "author": "Test Author",
            "license": "MIT",
        },
        "intent": {
            "learning_objective": "Understand model response patterns.",
            "behavioral_focus": "Critical reasoning",
        },
        "execution": {
            "system_prompt": "You are a helpful assistant.",
            "model_profile": "default",
        },
        "constraints": {
            "input_mode": "freeform",
            "turn_limit": 5,
        },
        "reflection": {
            "reflection_prompts": [
                "What did you learn?",
                "What surprised you?"
            ]
        },
        "schema_version": "1.0"
    }


@pytest.fixture
def valid_course_payload():
    return {
        "course_id": "CS101",
        "title": "Intro to AI",
        "description": "Foundations of language models",
        "instructor": "Dr. Test",
        "term": "Fall 2026",
        "owner_id": "ignored",
        "enrolled_users": ["tester","Alice", "Bob"],
        "discoverable": True,
        "lessons": {},
    }