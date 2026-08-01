import asyncio
import json

def run(coro):
    return asyncio.run(coro)


def test_app_builds(client, api_prefix, storage_backend):
    response = client.get("api/health")
    assert response.status_code == 200


def test_create_session_success(
    client,
    lesson_factory,
    course_factory,
    admin_headers,
    api_prefix,
    storage_backend,
):
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version

    course_id = course_factory()
    upload = client.post(
        f"{api_prefix}/courses/{course_id}/lesson-artifacts",
        json=lesson.model_dump(mode="json"),
        headers=admin_headers,
    )
    assert upload.status_code == 200
    binding = client.post(
        f"{api_prefix}/courses/{course_id}/lessons",
        json={"lesson_id": lesson_id, "version": lesson_version},
        headers=admin_headers,
    )
    assert binding.status_code == 200

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


def test_send_message_success(client, session_factory, api_prefix, storage_backend):
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


def test_stream_message_emits_delta_then_canonical_completion(
    client,
    session_factory,
    api_prefix,
    storage_backend,
):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"
    path = (
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}"
        f"/sessions/{session_id}/messages/stream"
    )

    response = client.post(
        path,
        json={"content": "Hello stream", "message_id": "stream-api-1"},
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert "event: delta\n" in response.text
    assert "event: complete\n" in response.text

    complete_frame = next(
        frame for frame in response.text.split("\n\n")
        if frame.startswith("event: complete\n")
    )
    complete_payload = json.loads(
        next(line[6:] for line in complete_frame.splitlines() if line.startswith("data: "))
    )
    assert complete_payload["assistant_message"]["role"] == "assistant"
    assert complete_payload["session"]["turn_count"] == 1

    retry = client.post(
        path.removesuffix("/stream"),
        json={"content": "Hello stream", "message_id": "stream-api-1"},
        headers={"X-User-Id": "tester"},
    )
    assert retry.status_code == 200
    assert retry.json()["session"]["turn_count"] == 1
    assert retry.json()["assistant_message"] == complete_payload["assistant_message"]


def test_stream_message_reports_non_fallback_domain_error(
    client,
    session_factory,
    api_prefix,
    storage_backend,
):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"
    base_path = (
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}"
        f"/sessions/{session_id}/messages"
    )
    first = client.post(
        base_path,
        json={"content": "Trigger the mid reflection", "message_id": "first-turn"},
        headers={"X-User-Id": "tester"},
    )
    assert first.status_code == 200

    response = client.post(
        f"{base_path}/stream",
        json={"content": "Blocked turn", "message_id": "blocked-turn"},
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    error_frame = next(
        frame for frame in response.text.split("\n\n")
        if frame.startswith("event: error\n")
    )
    error_payload = json.loads(
        next(line[6:] for line in error_frame.splitlines() if line.startswith("data: "))
    )
    assert error_payload["code"] == "reflection_required"
    assert error_payload["fallback_allowed"] is False


def test_get_session(client, session_factory, api_prefix, storage_backend):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.json()["session"]["session_id"] == session_id


def test_list_sessions_for_lesson(client, session_factory, api_prefix, storage_backend):
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


def test_list_sessions_orders_by_updated_at_after_message_send(client, session_factory, api_prefix, storage_backend):
    first_session_id, lesson_id, lesson_version = session_factory()
    second_session_id, _, _ = session_factory()
    course_id = "CS101"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{first_session_id}/messages",
        json={"content": "Move this session to the top"},
        headers={"X-User-Id": "tester"},
    )
    assert response.status_code == 200

    listed = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "tester"},
    )
    assert listed.status_code == 200
    sessions = listed.json()["sessions"]
    assert [session["session_id"] for session in sessions] == [
        first_session_id,
        second_session_id,
    ]


def test_close_session(client, session_factory, api_prefix, storage_backend):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/close",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_delete_session(client, session_factory, api_prefix, storage_backend):
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


def test_create_session_lesson_not_found(client, api_prefix, storage_backend):
    course_id = "CS101"
    lesson_id = "does_not_exist"
    lesson_version = "0.1.0"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "tester"},
    )

    assert response.status_code == 404


def test_get_session_not_found(client, lesson_factory, api_prefix, storage_backend):
    course_id = "CS101"
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version
    
    response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/fake-id",
        headers={"X-User-Id": "tester"},
    )
    assert response.status_code == 404


def test_missing_user_header_returns_401(client, lesson_factory, api_prefix, storage_backend):
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version
    course_id = "CS101"

    response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        json={"lesson_id": "test", "lesson_version": "1.0"},
    )

    assert response.status_code == 401


def test_user_cannot_access_other_users_session(client, session_factory, lesson_factory, api_prefix, storage_backend):
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


def test_health_alive(client, storage_backend):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_ready_success(client, storage_backend):
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_course_creation_sets_owner(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
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
    assert data["instructor_ids"] == ["Dr. Test"]
    assert data["enrolled_users"] == ["tester", "Alice", "Bob"]
    assert data["pending_requests"] == []


def test_discoverable_courses_visible(client, course_factory, api_prefix, storage_backend):
    course_id = course_factory()

    response = client.get(f"{api_prefix}/courses", headers={"X-User-Id": "tester"})

    assert response.status_code == 200
    courses = response.json()["courses"]

    assert any(c["course_id"] == f"{course_id}" for c in courses)


def test_invite_only_hidden_from_uninvited_user_listing(
    client,
    admin_headers,
    valid_course_payload,
    api_prefix,
    storage_backend,
):
    payload = valid_course_payload
    payload["discoverable"] = False
    course_id = payload["course_id"]

    client.post(f"{api_prefix}/admin/courses", json=payload, headers=admin_headers)

    response = client.get(
        f"{api_prefix}/courses",
        headers={"X-User-Id": "uninvited-student"},
    )

    courses = response.json()["courses"]

    assert all(c["course_id"] != f"{course_id}" for c in courses)


def test_enrolled_user_sees_invite_only_course_in_listing(
    client,
    admin_headers,
    valid_course_payload,
    api_prefix,
    storage_backend,
):
    payload = valid_course_payload
    payload["discoverable"] = False
    course_id = payload["course_id"]

    client.post(f"{api_prefix}/admin/courses", json=payload, headers=admin_headers)

    response = client.get(f"{api_prefix}/courses", headers={"X-User-Id": "tester"})

    assert response.status_code == 200
    courses = response.json()["courses"]
    assert any(c["course_id"] == course_id for c in courses)


def test_owner_sees_invite_only_course_in_listing(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    payload = dict(valid_course_payload)
    payload["discoverable"] = False
    payload["owner_id"] = "instructor"
    payload["instructor_ids"] = ["instructor"]
    course_id = payload["course_id"]

    client.post(f"{api_prefix}/admin/courses", json=payload, headers=admin_headers)

    response = client.get(f"{api_prefix}/courses", headers={"X-User-Id": "instructor"})

    assert response.status_code == 200
    courses = response.json()["courses"]
    assert any(c["course_id"] == course_id for c in courses)


def test_parallel_instructor_sees_invite_only_course_in_listing(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    payload = dict(valid_course_payload)
    payload["discoverable"] = False
    payload["owner_id"] = "owner-1"
    payload["instructor_ids"] = ["owner-1", "assistant-1"]
    course_id = payload["course_id"]

    client.post(f"{api_prefix}/admin/courses", json=payload, headers=admin_headers)

    response = client.get(f"{api_prefix}/courses", headers={"X-User-Id": "assistant-1"})

    assert response.status_code == 200
    courses = response.json()["courses"]
    assert any(c["course_id"] == course_id for c in courses)


def test_enrollment_request_flow(client, course_factory, api_prefix, storage_backend):
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


def test_approval_moves_user_to_enrolled(client, course_factory, api_prefix, storage_backend):
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


def test_non_enrolled_cannot_access_course(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
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
    api_prefix,
    storage_backend,
):
    course_id = course_factory()
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version

    client.post(
        f"{api_prefix}/courses/{course_id}/lesson-artifacts",
        json=lesson.model_dump(mode="json"),
        headers=admin_headers,
    )
    client.post(
        f"{api_prefix}/courses/{course_id}/lessons",
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
    api_prefix,
    storage_backend,
):
    course_id = course_factory()
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version

    client.post(
        f"{api_prefix}/courses/{course_id}/lesson-artifacts",
        json=lesson.model_dump(mode="json"),
        headers=admin_headers,
    )
    client.post(
        f"{api_prefix}/courses/{course_id}/lessons",
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


def test_lesson_list(client, course_factory, lesson_factory, api_prefix, admin_headers, storage_backend):
    course_id = course_factory()
    lesson = lesson_factory()

    client.post(
        f"{api_prefix}/courses/{course_id}/lesson-artifacts",
        json=lesson.model_dump(mode="json"),
        headers=admin_headers,
    )
    bind_response = client.post(
        f"{api_prefix}/courses/CS101/lessons",
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


def test_student_course_and_lesson_projections_hide_private_authoring_data(
    client,
    session_factory,
    api_prefix,
    storage_backend,
):
    _, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    course_response = client.get(
        f"{api_prefix}/courses/{course_id}",
        headers={"X-User-Id": "tester"},
    )
    lessons_response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons",
        headers={"X-User-Id": "tester"},
    )

    assert course_response.status_code == 200
    assert "owner_id" not in course_response.json()
    assert "instructor_ids" not in course_response.json()
    assert "enrolled_users" not in course_response.json()
    assert "pending_requests" not in course_response.json()
    assert lessons_response.status_code == 200
    lesson_payload = next(
        item
        for item in lessons_response.json()["lessons"]
        if item["identity"]["lesson_id"] == lesson_id
        and item["identity"]["version"] == lesson_version
    )
    assert "execution" not in lesson_payload
    assert "constraints" not in lesson_payload
    assert "reflection" not in lesson_payload
    assert "system_prompt" not in lessons_response.text


def test_unenrollment_revokes_access_to_existing_sessions(
    client,
    session_factory,
    api_prefix,
    storage_backend,
):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    removed = client.post(
        f"{api_prefix}/courses/{course_id}/remove",
        json={"user_id": "tester"},
        headers={"X-User-Id": "ignored"},
    )
    assert removed.status_code == 200

    session_response = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}"
        f"/sessions/{session_id}",
        headers={"X-User-Id": "tester"},
    )
    message_response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}"
        f"/sessions/{session_id}/messages",
        json={"content": "This should be revoked."},
        headers={"X-User-Id": "tester"},
    )

    assert session_response.status_code == 404
    assert message_response.status_code == 404


def test_lesson_edit_affects_new_sessions_but_preserves_existing_snapshot(
    client,
    session_factory,
    session_storage,
    api_prefix,
    storage_backend,
):
    first_session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"
    artifact_path = (
        f"{api_prefix}/courses/{course_id}/lesson-artifacts/{lesson_id}/{lesson_version}"
    )
    current = client.get(artifact_path, headers={"X-User-Id": "ignored"})
    assert current.status_code == 200
    old_prompt = current.json()["lesson"]["execution"]["system_prompt"]
    updated_lesson = current.json()["lesson"]
    updated_lesson["execution"]["system_prompt"] = "Updated private system prompt."

    updated = client.post(
        f"{api_prefix}/courses/{course_id}/lesson-artifacts"
        f"?expected_revision={current.json()['artifact_revision']}",
        json=updated_lesson,
        headers={"X-User-Id": "ignored"},
    )
    assert updated.status_code == 200
    second = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "tester"},
    )
    assert second.status_code == 201

    first_session = run(session_storage.get_session(first_session_id))
    second_session = run(session_storage.get_session(second.json()["session"]["session_id"]))
    assert first_session is not None and first_session.lesson_snapshot is not None
    assert second_session is not None and second_session.lesson_snapshot is not None
    assert first_session.lesson_snapshot.execution.system_prompt == old_prompt
    assert second_session.lesson_snapshot.execution.system_prompt == "Updated private system prompt."
    assert first_session.lesson_artifact_revision < second_session.lesson_artifact_revision


def test_discoverable_courses_order_by_last_accessed(
    client,
    admin_headers,
    valid_course_payload,
    api_prefix,
    storage_backend,
):
    first_payload = dict(valid_course_payload)
    first_payload["course_id"] = "CS101"
    first_payload["title"] = "Course One"
    second_payload = dict(valid_course_payload)
    second_payload["course_id"] = "CS102"
    second_payload["title"] = "Course Two"

    assert client.post(f"{api_prefix}/admin/courses", json=first_payload, headers=admin_headers).status_code == 200
    assert client.post(f"{api_prefix}/admin/courses", json=second_payload, headers=admin_headers).status_code == 200

    touched = client.get(f"{api_prefix}/courses/CS101", headers={"X-User-Id": "tester"})
    assert touched.status_code == 200

    listed = client.get(f"{api_prefix}/courses", headers={"X-User-Id": "tester"})
    assert listed.status_code == 200
    assert [course["course_id"] for course in listed.json()["courses"]][:2] == ["CS101", "CS102"]


def test_lesson_list_orders_last_accessed_first_and_pinned_second(
    client,
    admin_headers,
    valid_course_payload,
    valid_lesson_payload,
    api_prefix,
    storage_backend,
):
    alpha_payload = dict(valid_lesson_payload)
    alpha_payload["identity"] = dict(valid_lesson_payload["identity"])
    alpha_payload["identity"]["lesson_id"] = "alpha"
    alpha_payload["identity"]["title"] = "Alpha"

    beta_payload = dict(valid_lesson_payload)
    beta_payload["identity"] = dict(valid_lesson_payload["identity"])
    beta_payload["identity"]["lesson_id"] = "beta"
    beta_payload["identity"]["title"] = "Beta"

    gamma_payload = dict(valid_lesson_payload)
    gamma_payload["identity"] = dict(valid_lesson_payload["identity"])
    gamma_payload["identity"]["lesson_id"] = "gamma"
    gamma_payload["identity"]["title"] = "Gamma"

    course_payload = dict(valid_course_payload)
    course_payload["lessons"] = {}
    course_payload["lesson_timeline"] = []
    created = client.post(f"{api_prefix}/admin/courses", json=course_payload, headers=admin_headers)
    assert created.status_code == 200

    for payload in [alpha_payload, beta_payload, gamma_payload]:
        response = client.post(
            f"{api_prefix}/courses/{course_payload['course_id']}/lesson-artifacts",
            json=payload,
            headers=admin_headers,
        )
        assert response.status_code == 200
        bound = client.post(
            f"{api_prefix}/courses/{course_payload['course_id']}/lessons",
            json={
                "lesson_id": payload["identity"]["lesson_id"],
                "version": payload["identity"]["version"],
            },
            headers=admin_headers,
        )
        assert bound.status_code == 200

    timeline = [
        {
            "lesson_id": "beta",
            "lesson_version": "0.1.0",
            "starts_at": "2026-01-01T00:00:00Z",
        }
    ]
    updated = client.put(
        f"{api_prefix}/courses/{course_payload['course_id']}/lesson-timeline",
        json={"lesson_timeline": timeline},
        headers={"X-User-Id": "ignored"},
    )
    assert updated.status_code == 200

    touched = client.get(
        f"{api_prefix}/courses/{course_payload['course_id']}/lessons",
        headers={"X-User-Id": "tester"},
    )
    assert touched.status_code == 200
    initial_ids = [lesson["identity"]["lesson_id"] for lesson in touched.json()["lessons"]]
    assert initial_ids[:2] == ["beta", "alpha"]

    session_response = client.post(
        f"{api_prefix}/courses/{course_payload['course_id']}/lessons/gamma/0.1.0/sessions",
        headers={"X-User-Id": "tester"},
    )
    assert session_response.status_code == 201

    listed = client.get(
        f"{api_prefix}/courses/{course_payload['course_id']}/lessons",
        headers={"X-User-Id": "tester"},
    )
    assert listed.status_code == 200
    ordered_ids = [lesson["identity"]["lesson_id"] for lesson in listed.json()["lessons"]]
    assert ordered_ids[:3] == ["gamma", "beta", "alpha"]


def test_owner_can_add_and_remove_parallel_instructor(client, course_factory, api_prefix, storage_backend):
    course_id = course_factory()

    add_response = client.post(
        f"{api_prefix}/courses/{course_id}/instructors",
        json={"user_id": "assistant-1"},
        headers={"X-User-Id": "ignored"},
    )

    assert add_response.status_code == 200
    assert add_response.json()["owner_id"] == "ignored"
    assert add_response.json()["instructor_ids"] == ["ignored", "assistant-1"]

    list_response = client.get(
        f"{api_prefix}/courses/{course_id}/instructors",
        headers={"X-User-Id": "assistant-1"},
    )

    assert list_response.status_code == 200
    assert list_response.json()["instructor_ids"] == ["ignored", "assistant-1"]

    remove_response = client.delete(
        f"{api_prefix}/courses/{course_id}/instructors/assistant-1",
        headers={"X-User-Id": "ignored"},
    )

    assert remove_response.status_code == 200
    assert remove_response.json()["instructor_ids"] == ["ignored"]


def test_owner_cannot_be_removed_from_instructor_list(client, course_factory, api_prefix, storage_backend):
    course_id = course_factory()

    response = client.delete(
        f"{api_prefix}/courses/{course_id}/instructors/ignored",
        headers={"X-User-Id": "ignored"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Owner cannot be removed from instructor list"


def test_instructor_log_access_boundary(client, session_factory, artifact_storage, api_prefix, storage_backend):
    session_id, lesson_id, lesson_version = session_factory()
    course_id = "CS101"

    client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/messages",
        json={"content": "Loggable turn"},
        headers={"X-User-Id": "tester"},
    )

    client.post(
        f"{api_prefix}/courses/{course_id}/instructors",
        json={"user_id": "assistant-1"},
        headers={"X-User-Id": "ignored"},
    )

    owner_logs = client.get(
        f"{api_prefix}/courses/{course_id}/logs",
        headers={"X-User-Id": "ignored"},
    )
    assert owner_logs.status_code == 200
    assert len(owner_logs.json()["logs"]) == 1
    assert owner_logs.json()["logs"][0]["instance_id"] == session_id

    assistant_logs = client.get(
        f"{api_prefix}/courses/{course_id}/logs",
        headers={"X-User-Id": "assistant-1"},
    )
    assert assistant_logs.status_code == 200
    assert len(assistant_logs.json()["logs"]) == 1

    assistant_log = client.get(
        f"{api_prefix}/courses/{course_id}/logs/{session_id}",
        headers={"X-User-Id": "assistant-1"},
    )
    assert assistant_log.status_code == 200
    assert assistant_log.json()["session"]["session_id"] == session_id

    learner_log_list = client.get(
        f"{api_prefix}/courses/{course_id}/logs",
        headers={"X-User-Id": "tester"},
    )
    assert learner_log_list.status_code == 404

    outsider_log = client.get(
        f"{api_prefix}/courses/{course_id}/logs/{session_id}",
        headers={"X-User-Id": "outsider"},
    )
    assert outsider_log.status_code == 404
    audits = run(artifact_storage.list_encrypted_log_access_audits(course_id=course_id))
    assert len(audits) == 3
    assert [entry.action for entry in audits] == ["metadata_list", "metadata_list", "payload_read"]
    assert all(entry.requester_user_id in {"ignored", "assistant-1"} for entry in audits)


def test_parallel_instructor_can_create_own_session_but_list_only_their_own(
    client,
    course_factory,
    lesson_factory,
    api_prefix,
    admin_headers,
    storage_backend,
):
    course_id = course_factory()
    lesson = lesson_factory()
    lesson_id = lesson.identity.lesson_id
    lesson_version = lesson.identity.version

    client.post(
        f"{api_prefix}/courses/{course_id}/lesson-artifacts",
        json=lesson.model_dump(mode="json"),
        headers=admin_headers,
    )
    client.post(
        f"{api_prefix}/courses/{course_id}/lessons",
        json={"lesson_id": lesson_id, "version": lesson_version},
        headers=admin_headers,
    )
    client.post(
        f"{api_prefix}/courses/{course_id}/instructors",
        json={"user_id": "assistant-1"},
        headers={"X-User-Id": "ignored"},
    )
    learner_response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "tester"},
    )
    assert learner_response.status_code == 201

    instructor_response = client.post(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "assistant-1"},
    )
    assert instructor_response.status_code == 201
    instructor_session_id = instructor_response.json()["session"]["session_id"]
    assert instructor_response.json()["session"]["user_id"] == "assistant-1"

    listed = client.get(
        f"{api_prefix}/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        headers={"X-User-Id": "assistant-1"},
    )
    assert listed.status_code == 200
    sessions = listed.json()["sessions"]
    assert [session["session_id"] for session in sessions] == [instructor_session_id]
    assert all(session["user_id"] == "assistant-1" for session in sessions)
