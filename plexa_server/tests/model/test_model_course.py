import pytest
from pydantic import ValidationError
from datetime import UTC, datetime, timedelta

from plexa_server.models.course import Course


# Valid Course

def test_valid_course_parses(valid_course_payload):
    course = Course.model_validate(valid_course_payload)

    assert course.course_id == "CS101"
    assert course.title == "Intro to AI"
    assert isinstance(course.created_at, datetime)
    assert course.lessons == {}
    assert course.instructor_ids == ["ignored"]


# Missing Required Field

def test_missing_required_field_fails(valid_course_payload):
    broken = valid_course_payload
    broken.pop("title")

    with pytest.raises(ValidationError) as exc_info:
        Course.model_validate(broken)

    errors = exc_info.value.errors()

    assert any(
        err["loc"] == ("title",)
        for err in errors
    )


# Lessons Default Behavior

def test_lessons_default_is_empty_dict(valid_course_payload):
    payload = valid_course_payload
    payload.pop("lessons")

    course = Course.model_validate(payload)

    assert course.lessons == {}


# Type Enforcement

def test_lessons_must_be_mapping(valid_course_payload):
    broken = valid_course_payload
    broken["lessons"] = ["not", "a", "dict"]

    with pytest.raises(ValidationError):
        Course.model_validate(broken)


def test_owner_is_added_to_instructor_ids():
    course = Course.model_validate(
        {
            "course_id": "CS101",
            "title": "Intro to AI",
            "owner_id": "owner-1",
            "instructor_ids": ["assistant-1", "owner-1", "assistant-1"],
        }
    )

    assert course.instructor_ids == ["owner-1", "assistant-1"]


def test_course_timeline_must_reference_bound_lessons():
    with pytest.raises(ValidationError):
        Course.model_validate(
            {
                "course_id": "CS101",
                "title": "Intro to AI",
                "owner_id": "owner-1",
                "lessons": {},
                "lesson_timeline": [
                    {
                        "lesson_id": "lesson-1",
                        "lesson_version": "0.1.0",
                        "starts_at": datetime.now(UTC).isoformat(),
                    }
                ],
            }
        )


def test_course_timeline_rejects_overlapping_windows():
    start = datetime.now(UTC)
    with pytest.raises(ValidationError):
        Course.model_validate(
            {
                "course_id": "CS101",
                "title": "Intro to AI",
                "owner_id": "owner-1",
                "lessons": {
                    "lesson-1": "0.1.0",
                    "lesson-2": "0.1.0",
                },
                "lesson_timeline": [
                    {
                        "lesson_id": "lesson-1",
                        "lesson_version": "0.1.0",
                        "starts_at": start.isoformat(),
                        "ends_at": (start + timedelta(days=1)).isoformat(),
                    },
                    {
                        "lesson_id": "lesson-2",
                        "lesson_version": "0.1.0",
                        "starts_at": (start + timedelta(hours=12)).isoformat(),
                        "ends_at": (start + timedelta(days=2)).isoformat(),
                    },
                ],
            }
        )
