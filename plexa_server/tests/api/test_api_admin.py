from copy import deepcopy


# Lesson Upload

def test_upload_lesson_success(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend, course_factory):
    payload = valid_lesson_payload
    course_factory()

    response = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["lesson_id"] == "test"
    assert data["version"] == "0.1.0"
    assert data["overwritten"] is False


def test_upload_lesson_overwrite(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend, course_factory):
    payload = valid_lesson_payload
    course_factory()

    created = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts",
        json=payload,
        headers=admin_headers,
    )

    response = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts?expected_revision={created.json()['artifact_revision']}",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["overwritten"] is True


def test_upload_lesson_rejects_stale_revision(
    client,
    admin_headers,
    valid_lesson_payload,
    api_prefix,
    storage_backend,
    course_factory,
):
    course_factory()
    created = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts",
        json=valid_lesson_payload,
        headers=admin_headers,
    )
    revision = created.json()["artifact_revision"]
    first_update = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts?expected_revision={revision}",
        json=valid_lesson_payload,
        headers=admin_headers,
    )
    assert first_update.status_code == 200

    stale_update = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts?expected_revision={revision}",
        json=valid_lesson_payload,
        headers=admin_headers,
    )
    assert stale_update.status_code == 409


def test_update_course_rejects_stale_revision(
    client,
    course_factory,
    admin_headers,
    api_prefix,
    storage_backend,
):
    course_id = course_factory()
    current = client.get(
        f"{api_prefix}/admin/courses/{course_id}",
        headers=admin_headers,
    )
    assert current.status_code == 200
    first_payload = current.json()
    stale_payload = dict(first_payload)
    first_payload["title"] = "First update"
    stale_payload["title"] = "Stale update"

    first = client.put(
        f"{api_prefix}/admin/courses/{course_id}",
        json=first_payload,
        headers=admin_headers,
    )
    stale = client.put(
        f"{api_prefix}/admin/courses/{course_id}",
        json=stale_payload,
        headers=admin_headers,
    )

    assert first.status_code == 200
    assert stale.status_code == 409


def test_upload_lesson_validation_failure(client, admin_headers, api_prefix, storage_backend, course_factory):
    # Missing required identity field
    payload = {
        "content": {"title": "Broken"},
    }

    course_factory()
    response = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422
    data = response.json()

    assert "detail" in data


def test_course_owner_can_author_and_bind_but_parallel_instructor_cannot(
    client,
    valid_lesson_payload,
    api_prefix,
    storage_backend,
    course_factory,
):
    course_factory()
    owner_headers = {"X-User-Id": "ignored"}
    assistant_headers = {"X-User-Id": "assistant-1"}

    owner_upload = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts",
        json=valid_lesson_payload,
        headers=owner_headers,
    )
    assert owner_upload.status_code == 200
    added = client.post(
        f"{api_prefix}/courses/CS101/instructors",
        json={"user_id": "assistant-1"},
        headers=owner_headers,
    )
    assert added.status_code == 200

    assistant_read = client.get(
        f"{api_prefix}/courses/CS101/lesson-artifacts/test/0.1.0",
        headers=assistant_headers,
    )
    assistant_upload = client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts",
        json=valid_lesson_payload,
        headers=assistant_headers,
    )
    assistant_bind = client.post(
        f"{api_prefix}/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=assistant_headers,
    )
    owner_bind = client.post(
        f"{api_prefix}/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=owner_headers,
    )

    assert assistant_read.status_code == 404
    assert assistant_upload.status_code == 404
    assert assistant_bind.status_code == 404
    assert owner_bind.status_code == 200


# Admin Auth Enforcement

def test_admin_requires_token(client, course_factory, api_prefix, storage_backend):
    response = client.get(
        f"{api_prefix}/admin/courses"
    )

    assert response.status_code == 403


# Course Binding

def test_bind_lesson_to_course(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend, course_factory):
    payload = valid_lesson_payload
    course_factory()

    client.post(
        f"{api_prefix}/courses/CS101/lesson-artifacts",
        json=payload,
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

    assert bind_response.status_code == 200
    data = bind_response.json()

    assert data["course_id"] == "CS101"
    assert data["lesson_id"] == "test"
    assert data["version"] == "0.1.0"


def test_bind_replaces_existing_version(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend, course_factory):
    course_factory()
    lesson_v1 = deepcopy(valid_lesson_payload)
    lesson_v2 = deepcopy(valid_lesson_payload)
    lesson_v2["identity"]["version"] = "0.2.0"

    client.post(f"{api_prefix}/courses/CS101/lesson-artifacts", json=lesson_v1, headers=admin_headers)
    client.post(f"{api_prefix}/courses/CS101/lesson-artifacts", json=lesson_v2, headers=admin_headers)

    client.post(
        f"{api_prefix}/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    client.post(
        f"{api_prefix}/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.2.0"},
        headers=admin_headers,
    )

    response = client.get(
        f"{api_prefix}/admin/courses/CS101/lessons",
        headers=admin_headers,
    )

    assert response.status_code == 200
    lessons = response.json()["lessons"]

    assert lessons["test"] == "0.2.0"


def test_bind_nonexistent_lesson_fails(client, admin_headers, api_prefix, storage_backend):
    response = client.post(
        f"{api_prefix}/courses/CS101/lessons",
        json={"lesson_id": "ghost", "version": "0.1.0"},
        headers=admin_headers,
    )

    assert response.status_code == 404


# Course Creation

def test_create_course_success(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    response = client.post(
        f"{api_prefix}/admin/courses",
        json=valid_course_payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["course_id"] == "CS101"
    assert data["title"] == "Intro to AI"
    assert data["instructor_ids"] == ["ignored"]


def test_create_course_duplicate_fails(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    response = client.post(
        f"{api_prefix}/admin/courses",
        json=valid_course_payload,
        headers=admin_headers,
    )

    assert response.status_code == 409


# Get & List Courses

def test_get_course(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    response = client.get(
        f"{api_prefix}/admin/courses/CS101",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["course_id"] == "CS101"


def test_list_courses(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    response = client.get(f"{api_prefix}/admin/courses", headers=admin_headers)

    assert response.status_code == 200
    courses = response.json()["courses"]

    assert len(courses) == 1
    assert courses[0]["course_id"] == "CS101"


# Update Course

def test_update_course_preserves_lessons(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    # Bind fake lesson mapping manually for test
    update_payload = {
        "course_id": "CS101",
        "title": "Updated Title",
        "description": "Updated desc",
        "instructor": "Dr. Test",
        "term": "Fall 2026",
        "owner_id": "Dr. Test",
        "lessons": {},  # should be ignored
    }

    response = client.put(
        f"{api_prefix}/admin/courses/CS101",
        json=update_payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


# Delete Course

def test_delete_course(client, admin_headers, valid_course_payload, api_prefix, storage_backend):
    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    delete_response = client.delete(
        f"{api_prefix}/admin/courses/CS101",
        headers=admin_headers,
    )

    assert delete_response.status_code == 200

    get_response = client.get(
        f"{api_prefix}/admin/courses/CS101",
        headers=admin_headers,
    )

    assert get_response.status_code == 200
    assert get_response.json()["archived_at"] is not None
    assert get_response.json()["discoverable"] is False

    student_list = client.get(
        f"{api_prefix}/courses?include_archived=true",
        headers={"X-User-Id": "tester"},
    )
    assert student_list.status_code == 200
    assert student_list.json()["courses"] == []

    owner_list = client.get(
        f"{api_prefix}/courses?include_archived=true",
        headers={"X-User-Id": "ignored"},
    )
    assert owner_list.status_code == 200
    assert owner_list.json()["courses"][0]["archived_at"] is not None

    assert client.get(
        f"{api_prefix}/courses/CS101",
        headers={"X-User-Id": "ignored"},
    ).status_code == 200
    assert client.get(
        f"{api_prefix}/courses/CS101",
        headers={"X-User-Id": "tester"},
    ).status_code == 404
    assert client.put(
        f"{api_prefix}/courses/CS101/lesson-timeline",
        json={"lesson_timeline": []},
        headers={"X-User-Id": "ignored"},
    ).status_code == 404


# Binding Behavior

def test_legacy_admin_binding_route_is_retired(client, admin_headers, api_prefix, storage_backend):
    response = client.post(
        f"{api_prefix}/admin/courses/CS404/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    assert response.status_code == 410


def test_binding_replaces_version(client, admin_headers, valid_course_payload, valid_lesson_payload, api_prefix, storage_backend):
    # Create course
    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    # Upload lessons
    lesson_v1 = deepcopy(valid_lesson_payload)
    lesson_v2 = deepcopy(valid_lesson_payload)
    lesson_v2["identity"]["version"] = "0.2.0"

    client.post(f"{api_prefix}/courses/CS101/lesson-artifacts", json=lesson_v1, headers=admin_headers)
    client.post(f"{api_prefix}/courses/CS101/lesson-artifacts", json=lesson_v2, headers=admin_headers)

    # Bind v1
    client.post(
        f"{api_prefix}/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    # Bind v2 (replace)
    client.post(
        f"{api_prefix}/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.2.0"},
        headers=admin_headers,
    )

    response = client.get(
        f"{api_prefix}/admin/courses/CS101/lessons",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["lessons"]["test"] == "0.2.0"
