from fastapi import APIRouter, HTTPException, Depends, status
from datetime import UTC, datetime

from plexa_server.models.course import Course
from plexa_server.auth.dependencies import require_admin
from plexa_server.auth.identity import UserIdentity
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseRevisionConflictError,
    CourseStorage,
)


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

    async def save_course_or_409(course: Course) -> None:
        try:
            await course_storage.save_course(course)
        except CourseRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    # Upload Lesson

    @router.post("/lessons")
    async def upload_lesson(
        lesson_payload: dict,
        _: UserIdentity = Depends(require_admin),
    ):
        """Validate and persist a lesson payload, noting whether it overwrote an existing version.

        Args:
            lesson_payload: Raw lesson document submitted by the caller.
            _: Validated admin identity.

        Returns:
            dict | JSONResponse: Success metadata for the stored lesson, or a
            validation failure payload.
        """
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Use the course-scoped /courses/{course_id}/lesson-artifacts endpoint.",
        )


    # Get Lesson

    @router.get("/lessons/{lesson_id}/{version}")
    async def get_lesson(
        lesson_id: str,
        version: str,
        _: UserIdentity = Depends(require_admin),
    ):
        """Return a stored lesson artifact by lesson id and version.

        Args:
            lesson_id: Lesson identifier to load.
            version: Lesson version to load.
            _: Validated admin identity.

        Returns:
            Lesson: Stored lesson artifact.

        Raises:
            HTTPException: If the requested lesson does not exist.
        """
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Use the course-scoped lesson-artifact endpoint.",
        )


    # Create Course

    @router.post("/courses")
    async def create_course(
        payload: Course,
        _: UserIdentity = Depends(require_admin),
    ):
        """Persist a new course document if the course id is unused.

        Args:
            payload: Course payload to persist.
            _: Validated admin identity.

        Returns:
            Course: Persisted course payload.

        Raises:
            HTTPException: If a course with the same id already exists.
        """
        existing = await course_storage.get_course(payload.course_id)

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Course already exists",
            )
        if payload.lessons or payload.lesson_timeline:
            raise HTTPException(
                status_code=400,
                detail="Create the course first, then upload and bind course-scoped lessons.",
            )

        await save_course_or_409(payload)
        return payload


    # Get Course

    @router.get("/courses/{course_id}")
    async def get_course(
        course_id: str,
        _: UserIdentity = Depends(require_admin),
    ):
        """Return a stored course document for administrative access.

        Args:
            course_id: Course identifier to load.
            _: Validated admin identity.

        Returns:
            Course: Stored course document.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        course = await course_storage.get_course(course_id)

        if course is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

        return course


    # List Courses

    @router.get("/courses")
    async def list_courses(
        _: UserIdentity = Depends(require_admin),
    ):
        """List all persisted courses for administrative inspection.

        Args:
            _: Validated admin identity.

        Returns:
            dict: Mapping containing all persisted courses.
        """
        courses = await course_storage.list_courses()
        return {"courses": courses}


    # Update Course (metadata only)

    @router.put("/courses/{course_id}")
    async def update_course(
        course_id: str,
        payload: Course,
        _: UserIdentity = Depends(require_admin),
    ):
        """Replace course metadata while preserving existing lesson bindings.

        Args:
            course_id: Course identifier to update.
            payload: Replacement course payload.
            _: Validated admin identity.

        Returns:
            Course: Updated course payload with preserved lesson bindings.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        existing = await course_storage.get_course(course_id)

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )
        if payload.course_id != course_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Path course_id does not match payload course_id.",
            )

        # Preserve lesson bindings
        payload.lessons = existing.lessons
        payload.lesson_timeline = existing.lesson_timeline

        await save_course_or_409(payload)
        return payload


    # Delete Course

    @router.delete("/courses/{course_id}")
    async def delete_course(
        course_id: str,
        _: UserIdentity = Depends(require_admin),
    ):
        """Delete a persisted course document.

        Args:
            course_id: Course identifier to delete.
            _: Validated admin identity.

        Returns:
            dict: Deletion status payload.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        existing = await course_storage.get_course(course_id)

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

        existing.archived_at = datetime.now(UTC)
        existing.discoverable = False
        await save_course_or_409(existing)

        return {
            "status": "archived",
            "course_id": course_id,
        }


    # Bind Lesson to Course

    @router.post("/courses/{course_id}/lessons")
    async def bind_lesson(
        course_id: str,
        payload: dict,
        _: UserIdentity = Depends(require_admin),
    ):
        """Bind or replace a lesson version in the course's lesson mapping.

        Args:
            course_id: Course identifier whose lesson mapping should change.
            payload: Mapping containing `lesson_id` and `version`.
            _: Validated admin identity.

        Returns:
            dict | JSONResponse: Binding success payload, or a validation
            failure payload when required fields are missing.

        Raises:
            HTTPException: If the requested lesson does not exist.
        """
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Use the course-scoped /courses/{course_id}/lessons endpoint.",
        )


    # Get Course Lessons

    @router.get("/courses/{course_id}/lessons")
    async def get_course_lessons(
        course_id: str,
        _: UserIdentity = Depends(require_admin),
    ):
        """Return the raw persisted lesson bindings for a course.

        Args:
            course_id: Course identifier whose lesson bindings should be read.
            _: Validated admin identity.

        Returns:
            dict: Raw persisted course document containing lesson bindings.

        Raises:
            HTTPException: If the requested course does not exist.
        """
        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )
        return course.model_dump(mode="json")

    return router
