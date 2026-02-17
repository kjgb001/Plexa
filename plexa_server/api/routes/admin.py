from fastapi import APIRouter, Header, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from pathlib import Path
import os
import json

from plexa_server.models.lesson import Lesson
from plexa_server.models.course import Course
from plexa_server.storage.filesystem import FileSystemArtifactStorage, FileSystemCourseStorage


# Admin Auth Dependency

def require_admin_token(
    token: str | None = Header(default=None, alias="X-Admin-Token")
) -> str:
    expected = os.getenv("PLEXA_ADMIN_TOKEN")
    if expected is None:
        raise HTTPException(
            status_code=500,
            detail="Admin token not configured"
        )

    if token is None or token != expected:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin token"
        )

    return token


# Router Factory

def get_admin_router(
    artifact_storage: FileSystemArtifactStorage,
    course_storage: FileSystemCourseStorage
) -> APIRouter:

    router = APIRouter(prefix="/admin", tags=["admin"])

    # Upload Lesson

    @router.post("/lessons")
    def upload_lesson(
        lesson_payload: dict,
        _: str = Depends(require_admin_token),
    ):
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
        courses = course_storage.list_courses()
        return {"courses": courses}


    # Update Course (metadata only)

    @router.put("/courses/{course_id}")
    def update_course(
        course_id: str,
        payload: Course,
        _: str = Depends(require_admin_token),
    ):
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

        # Course storage path
        courses_dir = artifact_storage.base_path / "configs" / "courses"
        courses_dir.mkdir(parents=True, exist_ok=True)

        course_path = courses_dir / f"{course_id}.json"

        if course_path.exists():
            with open(course_path, "r") as f:
                course_data = json.load(f)
        else:
            course_data = {
                "course_id": course_id,
                "lessons": {},
            }

        # Replace or insert
        course_data["lessons"][lesson_id] = version

        with open(course_path, "w") as f:
            json.dump(course_data, f, indent=2)

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
