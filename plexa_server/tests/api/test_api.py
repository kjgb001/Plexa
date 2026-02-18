from fastapi.testclient import TestClient

from plexa_server.storage.filesystem import FileSystemArtifactStorage
from plexa_server.models.lesson import Lesson, LessonIdentity


def test_app_builds(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_create_session_success(client, lesson_factory, course_factory):
    lesson_factory()
    course_id = course_factory()

    response = client.post(
        "/sessions",
        json={
            "lesson_id": "test",
            "lesson_version": "0.1.0",
        },
        headers={"X-User-Id": "tester", "X-Course-Id": "CS101"},
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
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["assistant_message"]["role"] == "assistant"
    assert "content" in data["assistant_message"]
    assert data["session"]["turn_count"] >= 1


def test_get_session(client, session_factory):
    session_id = session_factory()

    response = client.get(
        f"/sessions/{session_id}",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.json()["session"]["session_id"] == session_id


def test_close_session(client, session_factory):
    session_id = session_factory()

    response = client.post(
        f"/sessions/{session_id}/close",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_create_session_lesson_not_found(client):
    response = client.post(
        "/sessions",
        json={
            "lesson_id": "does_not_exist",
            "lesson_version": "0.1.0",
        },
        headers={"X-User-Id": "tester", "X-Course-Id": "CS101"},
    )

    assert response.status_code == 404


def test_get_session_not_found(client):
    response = client.get(
        "/sessions/fake-id",
        headers={"X-User-Id": "tester"},
    )
    assert response.status_code == 404


def test_missing_user_header_returns_401(client, lesson_factory):
    lesson_factory()

    response = client.post(
        "/sessions",
        json={"lesson_id": "test", "lesson_version": "1.0"},
    )

    assert response.status_code == 401


def test_user_cannot_access_other_users_session(client, session_factory):
    session_id = session_factory(user_id="Alice")

    response = client.get(
        f"/sessions/{session_id}",
        headers={"X-User-Id": "Bob"},
    )

    assert response.status_code == 404


def test_health_alive(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_ready_success(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_course_creation_sets_owner(client, admin_headers, valid_course_payload):
    payload = valid_course_payload
    payload["owner_id"] = "Dr. Test"

    response = client.post(
        "/admin/courses",
        json=valid_course_payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["owner_id"] == "Dr. Test"
    assert data["enrolled_users"] == ["tester", "Alice", "Bob"]
    assert data["pending_requests"] == []


def test_discoverable_courses_visible(client, course_factory):
    course_factory()

    response = client.get("/courses", headers={"X-User-Id": "tester"})

    assert response.status_code == 200
    courses = response.json()["courses"]

    assert any(c["course_id"] == "CS101" for c in courses)


def test_invite_only_hidden_from_listing(client, admin_headers, valid_course_payload):
    payload = valid_course_payload
    payload["discoverable"] = False

    client.post("/admin/courses", json=payload, headers=admin_headers)

    response = client.get("/courses", headers={"X-User-Id": "tester"})

    courses = response.json()["courses"]

    assert all(c["course_id"] != "CS101" for c in courses)


def test_enrollment_request_flow(client, course_factory):
    course_factory()

    response = client.post(
        "/courses/CS101/enroll",
        headers={"X-User-Id": "testina"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"

    # Owner sees request
    requests = client.get(
        "/courses/CS101/requests",
        headers={"X-User-Id": "ignored"},
    )

    assert requests.status_code == 200
    assert "testina" in requests.json()["pending_requests"]


def test_approval_moves_user_to_enrolled(client, course_factory):
    course_factory()

    client.post(
        "/courses/CS101/enroll", 
        headers={"X-User-Id": "testina"}
    )

    approve = client.post(
        "/courses/CS101/approve",
        json={"user_id": "testina"},
        headers={"X-User-Id": "ignored"},
    )

    assert approve.status_code == 200
    assert approve.json() == {"status":"approved"}

    course = client.get(
        "/courses/CS101",
        headers={"X-User-Id": "ignored"},
    )

    assert course.status_code == 200
    assert "testina" in course.json()["enrolled_users"]


def test_non_enrolled_cannot_access_course(client, admin_headers, valid_course_payload):
    valid_course_payload["discoverable"] = False
    client.post("/admin/courses", json=valid_course_payload, headers=admin_headers)

    response = client.get(
        "/courses/CS101",
        headers={"X-User-Id": "not enrolled"},
    )

    assert response.status_code == 404


def test_session_creation_requires_enrollment(
    client,
    admin_headers,
    course_factory,
    lesson_factory
):
    course_factory()
    lesson_factory()

    client.post(
        "/admin/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    response = client.post(
        "/sessions",
        json={
            "lesson_id": "test",
            "lesson_version": "0.1.0",
            "course_id": "CS101",
        },
        headers={"X-User-Id": "not enrolled", "X-Course-Id": "CS101"},
    )

    assert response.status_code == 404


def test_session_creation_after_enrollment(
    client,
    admin_headers,
    course_factory,
    lesson_factory
):
    course_factory()
    lesson_factory()

    client.post(
        "/admin/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    client.post(
        "/courses/CS101/enroll", 
        headers={"X-User-Id": "testina"}
    )

    approve = client.post(
        "/courses/CS101/approve",
        json={"user_id": "testina"},
        headers={"X-User-Id": "ignored"},
    )

    response = client.post(
        "/sessions",
        json={
            "lesson_id": "test",
            "lesson_version": "0.1.0",
            "course_id": "CS101",
        },
        headers={"X-User-Id": "testina", "X-Course-Id": "CS101"},
    )

    assert response.status_code == 201