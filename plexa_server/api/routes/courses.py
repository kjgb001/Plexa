from fastapi import APIRouter, HTTPException, Depends

from plexa_server.auth.dependencies import (
    ensure_course_instructor,
    ensure_course_owner,
    ensure_enrolled_or_owner,
    require_identity,
)
from plexa_server.auth.identity import UserIdentity
from plexa_server.core.encrypted_logs import EncryptedLogService
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage
from plexa_server.api.schemas.responses import (
    CourseInstructorsResponse,
    CourseLessonsResponse,
    EncryptedLogListResponse,
    EncryptedLogMetadataResponse,
)


def get_course_router(
    course_storage: CourseStorage,
    artifact_storage: ArtifactStorage,
    encrypted_log_service: EncryptedLogService | None = None,
) -> APIRouter:
    """Create learner-facing course discovery and enrollment endpoints.

    Args:
        course_storage: Course storage used for discovery and enrollment state.
        artifact_storage: Artifact storage used to load bound lessons.

    Returns:
        APIRouter: Router exposing learner-facing course endpoints.
    """

    router = APIRouter(prefix="/courses", tags=["courses"])

    @router.get("")
    async def list_discoverable_courses(
        _: UserIdentity = Depends(require_identity)
    ):
        """List courses that are currently marked discoverable.

        Args:
            user_id: Caller identity resolved from the request header.

        Returns:
            dict: Mapping containing discoverable course documents.
        """
        courses = await course_storage.list_courses()

        visible = [
            c for c in courses
            if c.discoverable
        ]

        return {"courses": visible}

    @router.get("/{course_id}")
    async def get_course(
        course_id: str,
        identity: UserIdentity = Depends(require_identity)
    ):
        """Return course metadata when the caller is allowed to view it.

        Args:
            course_id: Course identifier to load.
            user_id: Caller identity resolved from the request header.

        Returns:
            Course: Visible course document.

        Raises:
            HTTPException: If the course does not exist or is not visible to
                the caller.
        """
        course = await course_storage.get_course(course_id)

        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")

        if (
            course.discoverable
            or course.has_instructor_access(identity.user_id)
            or identity.user_id in course.enrolled_users
        ):
            return course

        raise HTTPException(status_code=404, detail="Course not found")


    @router.get("/{course_id}/lessons")
    async def get_course_lessons(
        course_id: str,
        identity: UserIdentity = Depends(require_identity)
    ) -> CourseLessonsResponse:
        """Return lesson documents for a course visible to the caller.

        Args:
            course_id: Course identifier whose lessons should be loaded.
            user_id: Caller identity resolved from the request header.

        Returns:
            list: Lesson documents bound to the requested course.

        Raises:
            HTTPException: If the course does not exist or is not visible to
                the caller.
        """
        course = await course_storage.get_course(course_id)

        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        if not course.discoverable and not course.has_instructor_access(identity.user_id) and identity.user_id not in course.enrolled_users:
            raise HTTPException(status_code=404, detail="Course not found")
        if not course.has_instructor_access(identity.user_id):
            ensure_enrolled_or_owner(course.owner_id, course.enrolled_users, identity)

        lessons = []
        for lesson_id, lesson_version in course.lessons.items():
            lesson = await artifact_storage.load_lesson(lesson_id, lesson_version)
            if lesson is not None:
                lessons.append(lesson)
        return CourseLessonsResponse(lessons=lessons)
        

    @router.post("/{course_id}/enroll")
    async def request_enrollment(
        course_id: str,
        identity: UserIdentity = Depends(require_identity)
    ):
        """Queue the caller for enrollment in a discoverable course.

        Args:
            course_id: Course identifier to request enrollment for.
            user_id: Caller identity resolved from the request header.

        Returns:
            dict: Enrollment status payload.

        Raises:
            HTTPException: If the course does not exist or is not discoverable.
        """
        course = await course_storage.get_course(course_id)

        if course is None or not course.discoverable:
            raise HTTPException(status_code=404, detail="Course not found")

        if identity.user_id in course.enrolled_users:
            return {"status": "already_enrolled"}

        if identity.user_id not in course.pending_requests:
            course.pending_requests.append(identity.user_id)
            await course_storage.save_course(course)

        return {"status": "pending"}


    @router.get("/{course_id}/requests")
    async def view_requests(
        course_id: str,
        identity: UserIdentity = Depends(require_identity)
    ):
        """Return pending enrollment requests for a course owner.

        Args:
            course_id: Course identifier whose pending requests should be read.
            user_id: Caller identity resolved from the request header.

        Returns:
            dict: Mapping containing pending enrollment requests.

        Raises:
            HTTPException: If the course does not exist or the caller is not
                the owner.
        """
        course = await course_storage.get_course(course_id)

        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)

        return {"pending_requests": course.pending_requests}


    @router.post("/{course_id}/approve")
    async def approve_student(
        course_id: str,
        payload: dict,
        identity: UserIdentity = Depends(require_identity)
    ):
        """Approve a pending learner and move them into the enrolled list.

        Args:
            course_id: Course identifier to update.
            payload: Mapping containing the `user_id` to approve.
            user_id: Caller identity resolved from the request header.

        Returns:
            dict: Approval status payload.

        Raises:
            HTTPException: If the course does not exist, the caller is not the
                owner, or the payload omits the target user.
        """
        target_user = payload.get("user_id")

        course = await course_storage.get_course(course_id)

        if course is None or target_user is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)

        if target_user in course.pending_requests:
            course.pending_requests.remove(target_user)

            if target_user not in course.enrolled_users:
                course.enrolled_users.append(target_user)

            await course_storage.save_course(course)

        return {"status": "approved"}


    @router.post("/{course_id}/remove")
    async def remove_student(
        course_id: str,
        payload: dict,
        identity: UserIdentity = Depends(require_identity)
    ):
        """Remove an enrolled learner from a course.

        Args:
            course_id: Course identifier to update.
            payload: Mapping containing the `user_id` to remove.
            user_id: Caller identity resolved from the request header.

        Returns:
            dict: Removal status payload.

        Raises:
            HTTPException: If the course does not exist, the caller is not the
                owner, or the payload omits the target user.
        """
        target_user = payload.get("user_id")

        course = await course_storage.get_course(course_id)

        if course is None or target_user is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)

        if target_user in course.enrolled_users:
            course.enrolled_users.remove(target_user)
            await course_storage.save_course(course)

        return {"status": "removed"}

    @router.get("/{course_id}/instructors", response_model=CourseInstructorsResponse)
    async def list_instructors(
        course_id: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> CourseInstructorsResponse:
        """Return the authorized instructor set for a course."""
        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_instructor(course, identity)
        return CourseInstructorsResponse(owner_id=course.owner_id, instructor_ids=course.instructor_ids)

    @router.post("/{course_id}/instructors", response_model=CourseInstructorsResponse)
    async def add_instructor(
        course_id: str,
        payload: dict,
        identity: UserIdentity = Depends(require_identity),
    ) -> CourseInstructorsResponse:
        """Add an authorized instructor to the course. Owner only."""
        target_user = payload.get("user_id")
        course = await course_storage.get_course(course_id)
        if course is None or target_user is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)
        if target_user not in course.instructor_ids:
            course.instructor_ids.append(target_user)
            await course_storage.save_course(course)
        return CourseInstructorsResponse(owner_id=course.owner_id, instructor_ids=course.instructor_ids)

    @router.delete("/{course_id}/instructors/{user_id}", response_model=CourseInstructorsResponse)
    async def remove_instructor(
        course_id: str,
        user_id: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> CourseInstructorsResponse:
        """Remove an authorized instructor from the course. Owner only."""
        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)
        if user_id == course.owner_id:
            raise HTTPException(status_code=400, detail="Owner cannot be removed from instructor list")
        if user_id in course.instructor_ids:
            course.instructor_ids.remove(user_id)
            await course_storage.save_course(course)
        return CourseInstructorsResponse(owner_id=course.owner_id, instructor_ids=course.instructor_ids)

    @router.get("/{course_id}/logs", response_model=EncryptedLogListResponse)
    async def list_encrypted_logs(
        course_id: str,
        lesson_id: str | None = None,
        lesson_version: str | None = None,
        user_id: str | None = None,
        identity: UserIdentity = Depends(require_identity),
    ) -> EncryptedLogListResponse:
        """List encrypted-log metadata for authorized instructors."""
        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_instructor(course, identity)
        if encrypted_log_service is None:
            raise HTTPException(status_code=503, detail="Encrypted logs unavailable")
        logs = await encrypted_log_service.list_session_log_metadata_for_requester(
            requester_user_id=identity.user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            lesson_version=lesson_version,
            user_id=user_id,
        )
        return EncryptedLogListResponse(
            logs=[EncryptedLogMetadataResponse.model_validate(log.model_dump()) for log in logs]
        )

    @router.get("/{course_id}/logs/{session_id}")
    async def get_encrypted_log(
        course_id: str,
        session_id: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> dict:
        """Return a decrypted session log for authorized instructors."""
        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_instructor(course, identity)
        if encrypted_log_service is None:
            raise HTTPException(status_code=503, detail="Encrypted logs unavailable")
        metadata = await artifact_storage.load_encrypted_log_metadata(session_id)
        if metadata is None or metadata.course_id != course_id:
            raise HTTPException(status_code=404, detail="Log not found")
        payload = await encrypted_log_service.load_session_log_for_requester(
            session_id=session_id,
            requester_user_id=identity.user_id,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="Log not found")
        return payload

    return router
