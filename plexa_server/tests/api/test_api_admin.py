import os
import json
import pytest


# Lesson Upload

def test_upload_lesson_success(client, admin_headers, valid_lesson_payload):
    payload = valid_lesson_payload

    response = client.post(
        "/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["lesson_id"] == "intro"
    assert data["version"] == "1.0"
    assert data["overwritten"] is False


def test_upload_lesson_overwrite(client, admin_headers, valid_lesson_payload):
    payload = valid_lesson_payload

    client.post("/admin/lessons", json=payload, headers=admin_headers)

    response = client.post(
        "/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["overwritten"] is True


def test_upload_lesson_validation_failure(client, admin_headers):
    # Missing required identity field
    payload = {
        "content": {"title": "Broken"},
    }

    response = client.post(
        "/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422
    data = response.json()

    assert data["error"] == "validation_failed"
    assert "details" in data


# Admin Auth Enforcement

def test_admin_requires_token(client):
    response = client.post(
        "/admin/lessons",
        json={},
    )

    assert response.status_code == 403


# Course Binding

def test_bind_lesson_to_course(client, admin_headers, valid_lesson_payload):
    payload = valid_lesson_payload

    client.post(
        "/admin/lessons",
        json=payload,
        headers=admin_headers,
    )

    bind_response = client.post(
        "/admin/courses/CS101/lessons",
        json={
            "lesson_id": "intro",
            "version": "1.0",
        },
        headers=admin_headers,
    )

    assert bind_response.status_code == 200
    data = bind_response.json()

    assert data["course_id"] == "CS101"
    assert data["lesson_id"] == "intro"
    assert data["version"] == "1.0"


def test_bind_replaces_existing_version(client, admin_headers, valid_lesson_payload):
    lesson_v1 = valid_lesson_payload

    lesson_v2 = valid_lesson_payload
    lesson_v2["identity"]["version"] = "2.0"

    client.post("/admin/lessons", json=lesson_v1, headers=admin_headers)
    client.post("/admin/lessons", json=lesson_v2, headers=admin_headers)

    client.post(
        "/admin/courses/CS101/lessons",
        json={"lesson_id": "intro", "version": "1.0"},
        headers=admin_headers,
    )

    client.post(
        "/admin/courses/CS101/lessons",
        json={"lesson_id": "intro", "version": "2.0"},
        headers=admin_headers,
    )

    response = client.get(
        "/admin/courses/CS101/lessons",
        headers=admin_headers,
    )

    assert response.status_code == 200
    lessons = response.json()["lessons"]

    assert lessons["intro"] == "2.0"


def test_bind_nonexistent_lesson_fails(client, admin_headers):
    response = client.post(
        "/admin/courses/CS101/lessons",
        json={"lesson_id": "ghost", "version": "1.0"},
        headers=admin_headers,
    )

    assert response.status_code == 404
