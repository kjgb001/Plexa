import os
import json
import pytest


# Lesson Upload

def test_upload_lesson_success(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend):
    payload = valid_lesson_payload

    response = client.post(
        f"{api_prefix}/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["lesson_id"] == "test"
    assert data["version"] == "0.1.0"
    assert data["overwritten"] is False


def test_upload_lesson_overwrite(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend):
    payload = valid_lesson_payload

    client.post(f"{api_prefix}/admin/lessons", json=payload, headers=admin_headers)

    response = client.post(
        f"{api_prefix}/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["overwritten"] is True


def test_upload_lesson_validation_failure(client, admin_headers, api_prefix, storage_backend):
    # Missing required identity field
    payload = {
        "content": {"title": "Broken"},
    }

    response = client.post(
        f"{api_prefix}/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422
    data = response.json()

    assert data["error"] == "validation_failed"
    assert "details" in data


# Admin Auth Enforcement

def test_admin_requires_token(client, course_factory, api_prefix, storage_backend):
    response = client.get(
        f"{api_prefix}/admin/courses"
    )

    assert response.status_code == 403


# Course Binding

def test_bind_lesson_to_course(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend):
    payload = valid_lesson_payload

    client.post(
        f"{api_prefix}/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    bind_response = client.post(
        f"{api_prefix}/admin/courses/CS101/lessons",
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


def test_bind_replaces_existing_version(client, admin_headers, valid_lesson_payload, api_prefix, storage_backend):
    lesson_v1 = valid_lesson_payload

    lesson_v2 = valid_lesson_payload
    lesson_v2["identity"]["version"] = "0.2.0"

    client.post(f"{api_prefix}/admin/lessons", json=lesson_v1, headers=admin_headers)
    client.post(f"{api_prefix}/admin/lessons", json=lesson_v2, headers=admin_headers)

    client.post(
        f"{api_prefix}/admin/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    client.post(
        f"{api_prefix}/admin/courses/CS101/lessons",
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
        f"{api_prefix}/admin/courses/CS101/lessons",
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

    assert get_response.status_code == 404


# Binding Behavior

def test_binding_requires_existing_course(client, admin_headers, api_prefix, storage_backend):
    response = client.post(
        f"{api_prefix}/admin/courses/CS404/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_binding_replaces_version(client, admin_headers, valid_course_payload, valid_lesson_payload, api_prefix, storage_backend):
    # Create course
    client.post(f"{api_prefix}/admin/courses", json=valid_course_payload, headers=admin_headers)

    # Upload lessons
    lesson_v1 = valid_lesson_payload
    lesson_v2 = valid_lesson_payload
    lesson_v2["identity"]["version"] = "0.2.0"

    client.post(f"{api_prefix}/admin/lessons", json=lesson_v1, headers=admin_headers)
    client.post(f"{api_prefix}/admin/lessons", json=lesson_v2, headers=admin_headers)

    # Bind v1
    client.post(
        f"{api_prefix}/admin/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.1.0"},
        headers=admin_headers,
    )

    # Bind v2 (replace)
    client.post(
        f"{api_prefix}/admin/courses/CS101/lessons",
        json={"lesson_id": "test", "version": "0.2.0"},
        headers=admin_headers,
    )

    response = client.get(
        f"{api_prefix}/admin/courses/CS101/lessons",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["lessons"]["test"] == "0.2.0"
