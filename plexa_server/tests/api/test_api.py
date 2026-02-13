from pathlib import Path
from fastapi.testclient import TestClient

from plexa_server.api.app import build_app
from plexa_server.storage.filesystem import FileSystemArtifactStorage
from plexa_server.models.lesson import Lesson, LessonIdentity


def test_app_builds(client):
    response = client.get("/docs")
    assert response.status_code == 200


def test_create_session_success(client, lesson_factory):
    lesson_factory()

    response = client.post(
        "/sessions",
        json={
            "lesson_id": "test",
            "lesson_version": "0.1.0",
            "user_id": "tester",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["session"]["user_id"] == "tester"
    assert data["session"]["lesson_id"] == "test"
    assert data["session"]["lesson_version"] == "0.1.0"
    assert data["session"]["is_active"] is True


def test_send_message_success(client, session_factory):
    session_id = session_factory()

    response = client.post(
        f"/sessions/{session_id}/messages",
        json={"content": "Hello world"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["assistant_message"]["role"] == "assistant"
    assert "content" in data["assistant_message"]
    assert data["session"]["turn_count"] >= 1


def test_get_session(client, session_factory):
    session_id = session_factory()

    response = client.get(f"/sessions/{session_id}")

    assert response.status_code == 200
    assert response.json()["session"]["session_id"] == session_id


def test_close_session(client, session_factory):
    session_id = session_factory()

    response = client.post(f"/sessions/{session_id}/close")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_create_session_lesson_not_found(client):
    response = client.post(
        "/sessions",
        json={
            "lesson_id": "does_not_exist",
            "lesson_version": "0.1.0",
            "user_id": "tester",
        },
    )

    assert response.status_code == 404


def test_get_session_not_found(client):
    response = client.get("/sessions/fake-id")
    assert response.status_code == 404

