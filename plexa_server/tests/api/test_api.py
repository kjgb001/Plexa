from fastapi.testclient import TestClient

from plexa_server.storage.filesystem import FileSystemArtifactStorage
from plexa_server.models.lesson import Lesson, LessonIdentity


def test_app_builds(client, api_prefix):
    response = client.get("api/health")
    assert response.status_code == 200


def test_create_session_success(client, lesson_factory, course_factory, api_prefix):
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version

    course_id = course_factory()

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 201

    data = response.json()
    assert data["session"]["user_id"] == "tester"
    assert data["session"]["course_id"] == course_id
    assert data["session"]["lesson_id"] == "test"
    assert data["session"]["lesson_version"] == "0.1.0"
    assert data["session"]["is_active"] is True


def test_send_message_success(client, session_factory, api_prefix):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/messages",
        json={"content": "Hello world"},
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200

    data = response.json()
    assert data["assistant_message"]["role"] == "assistant"
    assert "content" in data["assistant_message"]
    assert data["session"]["turn_count"] >= 1


def test_get_session(client, session_factory, api_prefix):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.json()["session"]["session_id"] == session_id


def test_list_sessions_for_lesson(client, session_factory, api_prefix):
    first_session_id, lesson_id, lesson_version = session_factory()
    second_session_id, _, _ = session_factory()
    session_factory(user_id="Alice")
    course_id = "CS101"

    response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200

    sessions = response.json()["sessions"]

    assert [session["session_id"] for session in sessions] == [
        second_session_id,
        first_session_id,
    ]
    assert all(session["user_id"] == "tester" for session in sessions)


def test_close_session(client, session_factory, api_prefix):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/close",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_delete_session(client, session_factory, api_prefix):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/delete",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "deleted",
        "session_id": session_id,
    }

    get_response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}",
        headers={"X-User-Id": "tester"},
    )

    assert get_response.status_code == 404


def test_create_session_lesson_not_found(client, api_prefix):
    course_id = "CS101"
    lesson_id = "does_not_exist"
    lesson_version = "0.1.0"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 404


def test_get_session_not_found(client, lesson_factory, api_prefix):
    course_id = "CS101"
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version
    
    response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/fake-id",
        headers={"X-User-Id": "tester"},
    )
    assert response.status_code == 404


def test_missing_user_header_returns_401(client, lesson_factory, api_prefix):
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version
    course_id = "CS101"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        json={"lesson_id": "test", "lesson_version": "1.0"},
    )

    assert response.status_code == 401


def test_user_cannot_access_other_users_session(client, session_factory, lesson_factory, api_prefix):
    session_id, lesson_id, lesson_version = session_factory(user_id="Alice")
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version
    course_id = "CS101"

    response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}",
        headers={"X-User-Id": "Bob"},
    )

    assert response.status_code == 404


def test_health_alive(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_ready_success(client):
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_course_creation_sets_owner(client, admin_headers, valid_course_payload, api_prefix):
    payload = valid_course_payload
    payload["owner_id"] = "Dr. Test"

    response = client.post(
        f"{api_prefix}/admin/courses",
        json=valid_course_payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["owner_id"] == "Dr. Test"
    assert data["enrolled_users"] == ["tester", "Alice", "Bob"]
    assert data["pending_requests"] == []


def test_discoverable_courses_visible(client, course_factory, api_prefix):
    course_id = course_factory()

    response = client.get(f"{api_prefix}/courses", headers={"X-User-Id": "tester"})

    assert response.status_code == 200
    courses = response.json()["courses"]

    assert any(c["course_id"] == f"{course_id}" for c in courses)


def test_invite_only_hidden_from_listing(client, admin_headers, valid_course_payload, api_prefix):
    payload = valid_course_payload
    payload["discoverable"] = False
    course_id = payload["course_id"]

    client.post(f"{api_prefix}/admin/courses", json=payload, headers=admin_headers)

    response = client.get(f"{api_prefix}/courses", headers={"X-User-Id": "tester"})

    courses = response.json()["courses"]

    assert all(c["course_id"] != f"{course_id}" for c in courses)


def test_enrollment_request_flow(client, course_factory, api_prefix):
    course_id = course_factory()

    response = client.post(
        f"{api_prefix}/courses/{course_id}/enroll",
        headers={"X-User-Id": "testina"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"

    # Owner sees request
    requests = client.get(
        f"{api_prefix}/courses/{course_id}/requests",
        headers={"X-User-Id": "ignored"},
    )

    assert requests.status_code == 200
    assert "testina" in requests.json()["pending_requests"]


def test_approval_moves_user_to_enrolled(client, course_factory, api_prefix):
    course_id = course_factory()

    client.post(
        f"{api_prefix}/courses/{course_id}/enroll", 
        headers={"X-User-Id": "testina"}
    )

    approve = client.post(
        f"{api_prefix}/courses/{course_id}/approve",
        json={"user_id": "testina"},
        headers={"X-User-Id": "ignored"},
    )

    assert approve.status_code == 200
    assert approve.json() == {"status":"approved"}

    course = client.get(
        f"{api_prefix}/courses/{course_id}",
        headers={"X-User-Id": "ignored"},
    )

    assert course.status_code == 200
    assert "testina" in course.json()["enrolled_users"]


def test_non_enrolled_cannot_access_course(client, admin_headers, valid_course_payload, api_prefix):
    valid_course_payload["discoverable"] = False
    course_id = valid_course_payload["course_id"]

    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    response = client.get(
        f"{api_prefix}/courses/{course_id}",
        headers={"X-User-Id": "not enrolled"},
    )

    assert response.status_code == 404


def test_session_creation_requires_enrollment(
    client,
    admin_headers,
    course_factory,
    lesson_factory,
    api_prefix
):
    course_id = course_factory()
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version

    client.post(
        f"{api_prefix}/admin/courses/{course_id}/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        json={
            "lesson_id": "test",
            "lesson_version": "0.1.0",
        },
        headers={"X-User-Id": "not enrolled"},
    )

    assert response.status_code == 404


def test_session_creation_after_enrollment(
    client,
    admin_headers,
    course_factory,
    lesson_factory,
    api_prefix
):
    course_id = course_factory()
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version

    client.post(
        f"{api_prefix}/admin/courses/{course_id}/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    client.post(
        f"{api_prefix}/courses/{course_id}/enroll", 
        headers={"X-User-Id": "testina"}
    )

    approve = client.post(
        f"{api_prefix}/courses/{course_id}/approve",
        json={"user_id": "testina"},
        headers={"X-User-Id": "ignored"},
    )

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "testina"},
    )

    assert response.status_code == 201


def test_lesson_list(client, course_factory, lesson_factory, api_prefix, admin_headers):
    course_id = course_factory()
    lesson_factory()

    bind_response = client.post(
        f"{api_prefix}/admin/courses/CS101/lessons",
        json={
            "lesson_id": "test",
            "version": "0.1.0",
        },
        headers=admin_headers,
    )

    response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons",
        headers={"X-User-Id": "tester"}
    )

    assert response.status_code == 200
    assert response.json()["lessons"][0]["identity"]["lesson_id"] == "test"
