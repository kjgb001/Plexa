from fastapi import APIRouter, Header, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pathlib import Path
import os
import json

from plexa_server.models.lesson import Lesson
from plexa_server.models.course import Course
from plexa_server.auth.admin import require_admin_token
from plexa_server.auth.user import require_user_id
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage


# Router Factory

def get_admin_router(
    artifact_storage: ArtifactStorage,
    course_storage: CourseStorage
) -> APIRouter:
    """Create administrative lesson and course management endpoints.

    Args:
        artifact_storage: Artifact storage used for lesson persistence.
        course_storage: Course storage used for course persistence.

    Returns:
        APIRouter: Router exposing admin-only lesson and course endpoints.
    """

    router = APIRouter(prefix="/admin", tags=["admin"])

    # Upload Lesson

    @router.post("/lessons")
    def upload_lesson(
        lesson_payload: dict,
        _: str = Depends(require_admin_token),
    ):
        """Validate and persist a lesson payload, noting whether it overwrote an existing version.

        Args:
            lesson_payload: Raw lesson document submitted by the caller.
            _: Validated admin token dependency value.

        Returns:
            dict | JSONResponse: Success metadata for the stored lesson, or a
            validation failure payload.
        """
        try:
            lesson = Lesson.model_validate(lesson_payload)
        except ValidationError as e:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "error": "validation_failed",
                    "message": "Lesson validation failed",
                    "details": e.errors(),
                },
            )

        existing = artifact_storage.load_lesson(
            lesson.identity.lesson_id,
            lesson.identity.version,
        )

        overwritten = existing is not None

        artifact_storage.save_lesson(lesson)

        return {
            "status": "ok",
            "lesson_id": lesson.identity.lesson_id,
            "version": lesson.identity.version,
            "overwritten": overwritten,
        }


    # Get Lesson

    @router.get("/lessons/{lesson_id}/{version}")
    def get_lesson(
        lesson_id: str,
        version: str,
        _: str = Depends(require_admin_token),
    ):
        """Return a stored lesson artifact by lesson id and version.

        Args:
            lesson_id: Lesson identifier to load.
            version: Lesson version to load.
            _: Validated admin token dependency value.

        Returns:
            Lesson: Stored lesson artifact.

        Raises:
            HTTPException: If the requested lesson does not exist.
        """
        lesson = artifact_storage.load_lesson(lesson_id, version)

        if lesson is None:
            raise HTTPException(
                status_code=404,
                detail="Lesson not found",
            )

        return lesson


    # Create Course

    @router.post("/courses")
    def create_course(
        payload: Course,
        _: str = Depends(require_admin_token),
    ):
        """Persist a new course document if the course id is unused.

        Args:
            payload: Course payload to persist.
            _: Validated admin token dependency value.

        Returns:
            Course: Persisted course payload.

        Raises:
            HTTPException: If a course with the same id already exists.
        """
        existing = course_storage.get_course(payload.course_id)

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Course already exists",
            )

        course_storage.save_course(payload)
        return payload


    # Get Course

    @router.get("/courses/{course_id}")
    def get_course(
        course_id: str,
        _: str = Depends(require_admin_token),
    ):
        """Return a stored course document for administrative access.

        Args:
            course_id: Course identifier to load.
            _: Validated admin token dependency value.

        Returns:
            Course: Stored course document.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        course = course_storage.get_course(course_id)

        if course is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

        return course


    # List Courses

    @router.get("/courses")
    def list_courses(
        _: str = Depends(require_admin_token),
    ):
        """List all persisted courses for administrative inspection.

        Args:
            _: Validated admin token dependency value.

        Returns:
            dict: Mapping containing all persisted courses.
        """
        courses = course_storage.list_courses()
        return {"courses": courses}


    # Update Course (metadata only)

    @router.put("/courses/{course_id}")
    def update_course(
        course_id: str,
        payload: Course,
        _: str = Depends(require_admin_token),
    ):
        """Replace course metadata while preserving existing lesson bindings.

        Args:
            course_id: Course identifier to update.
            payload: Replacement course payload.
            _: Validated admin token dependency value.

        Returns:
            Course: Updated course payload with preserved lesson bindings.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        existing = course_storage.get_course(course_id)

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

        # Preserve lesson bindings
        payload.lessons = existing.lessons

        course_storage.save_course(payload)
        return payload


    # Delete Course

    @router.delete("/courses/{course_id}")
    def delete_course(
        course_id: str,
        _: str = Depends(require_admin_token),
    ):
        """Delete a persisted course document.

        Args:
            course_id: Course identifier to delete.
            _: Validated admin token dependency value.

        Returns:
            dict: Deletion status payload.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        existing = course_storage.get_course(course_id)

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

        course_storage.delete_course(course_id)

        return {
            "status": "deleted",
            "course_id": course_id,
        }


    # Bind Lesson to Course

    @router.post("/courses/{course_id}/lessons")
    def bind_lesson(
        course_id: str,
        payload: dict,
        _: str = Depends(require_admin_token),
    ):
        """Bind or replace a lesson version in the course's lesson mapping.

        Args:
            course_id: Course identifier whose lesson mapping should change.
            payload: Mapping containing `lesson_id` and `version`.
            _: Validated admin token dependency value.

        Returns:
            dict | JSONResponse: Binding success payload, or a validation
            failure payload when required fields are missing.

        Raises:
            HTTPException: If the requested lesson does not exist.
        """
        lesson_id = payload.get("lesson_id")
        version = payload.get("version")

        if not lesson_id or not version:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "validation_failed",
                    "message": "lesson_id and version are required",
                    "details": [],
                },
            )

        lesson = artifact_storage.load_lesson(lesson_id, version)
        if lesson is None:
            raise HTTPException(
                status_code=404,
                detail="Lesson not found",
            )

        course_storage.bind_lesson_to_course(course_id, lesson_id, version)

        return {
            "status": "ok",
            "course_id": course_id,
            "lesson_id": lesson_id,
            "version": version,
        }


    # Get Course Lessons

    @router.get("/courses/{course_id}/lessons")
    def get_course_lessons(
        course_id: str,
        _: str = Depends(require_admin_token),
    ):
        """Return the raw persisted lesson bindings for a course.

        Args:
            course_id: Course identifier whose lesson bindings should be read.
            _: Validated admin token dependency value.

        Returns:
            dict: Raw persisted course document containing lesson bindings.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        course_path = (
            artifact_storage.base_path
            / "configs"
            / "courses"
            / f"{course_id}.json"
        )

        if not course_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

        with open(course_path, "r") as f:
            return json.load(f)

    return router
