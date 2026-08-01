from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import ValidationError

from plexa_server.auth.dependencies import (
    ensure_course_instructor,
    ensure_course_owner,
    ensure_enrolled_or_owner,
    require_identity,
)
from plexa_server.auth.identity import UserIdentity
from plexa_server.core.encrypted_logs import EncryptedLogService
from plexa_server.core.workspace import order_courses_for_user, order_lessons_for_user, resolve_pinned_lesson_window
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseRevisionConflictError,
    CourseStorage,
    LessonRevisionConflictError,
    WorkspaceStateStorage,
)
from plexa_server.api.schemas.requests import (
    CourseLessonTimelineRequest,
    LessonBindingRequest,
    UserTargetRequest,
)
from plexa_server.api.schemas.responses import (
    CourseSummaryResponse,
    InstructorCourseResponse,
    CourseInstructorsResponse,
    CourseLessonTimelineResponse,
    CourseLessonsResponse,
    EncryptedLogListResponse,
    EncryptedLogMetadataResponse,
    LessonSummaryResponse,
)


def get_course_router(
    course_storage: CourseStorage,
    artifact_storage: ArtifactStorage,
    encrypted_log_service: EncryptedLogService | None = None,
    workspace_state_storage: WorkspaceStateStorage | None = None,
) -> APIRouter:
    """Create learner-facing course discovery and enrollment endpoints.

    Args:
        course_storage: Course storage used for discovery and enrollment state.
        artifact_storage: Artifact storage used to load bound lessons.

    Returns:
        APIRouter: Router exposing learner-facing course endpoints.
    """

    router = APIRouter(prefix="/courses", tags=["courses"])

    def ensure_owner_or_admin(course: Course, identity: UserIdentity) -> None:
        if identity.is_admin or identity.user_id == course.owner_id:
            return
        raise HTTPException(status_code=404, detail="Course not found")

    def project_course(course: Course, identity: UserIdentity):
        common = dict(
            course_id=course.course_id,
            title=course.title,
            description=course.description,
            instructor=course.instructor,
            term=course.term,
            discoverable=course.discoverable,
            archived_at=course.archived_at,
            created_at=course.created_at,
            lessons=course.lessons,
            lesson_timeline=course.lesson_timeline,
            viewer_is_owner=identity.user_id == course.owner_id,
            viewer_is_instructor=course.has_instructor_access(identity.user_id),
            viewer_is_enrolled=identity.user_id in course.enrolled_users,
            viewer_has_pending_request=identity.user_id in course.pending_requests,
        )
        if identity.is_admin or course.has_instructor_access(identity.user_id):
            return InstructorCourseResponse(
                **common,
                owner_id=course.owner_id,
                instructor_ids=course.instructor_ids,
                enrolled_users=course.enrolled_users,
                pending_requests=course.pending_requests,
                revision=course.revision,
            )
        return CourseSummaryResponse(**common)

    async def save_course_or_409(course: Course) -> None:
        try:
            await course_storage.save_course(course)
        except CourseRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("")
    async def list_discoverable_courses(
        include_archived: bool = False,
        _: UserIdentity = Depends(require_identity),
    ):
        """List courses visible to the caller in the student portal.

        Args:
            user_id: Caller identity resolved from the request header.

        Returns:
            dict: Mapping containing course documents visible to the caller.
        """
        courses = await course_storage.list_courses()
        course_states = []
        if workspace_state_storage is not None:
            course_states = await workspace_state_storage.list_course_states(_.user_id)

        visible = []
        for course in courses:
            if course.archived_at is not None:
                if include_archived and (
                    _.is_admin or course.has_instructor_access(_.user_id)
                ):
                    visible.append(course)
                continue
            if (
                course.discoverable
                or _.is_admin
                or course.has_instructor_access(_.user_id)
                or _.user_id in course.enrolled_users
            ):
                visible.append(course)
        visible = order_courses_for_user(visible, course_states)

        return {"courses": [project_course(course, _) for course in visible]}

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

        if course.archived_at is not None:
            ensure_course_instructor(course, identity)
            return project_course(course, identity)

        if (
            course.discoverable
            or identity.is_admin
            or course.has_instructor_access(identity.user_id)
            or identity.user_id in course.enrolled_users
        ):
            if workspace_state_storage is not None:
                await workspace_state_storage.touch_course(identity.user_id, course_id)
            return project_course(course, identity)

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
        if course.archived_at is not None:
            ensure_course_instructor(course, identity)
        if (
            not identity.is_admin
            and not course.discoverable
            and not course.has_instructor_access(identity.user_id)
            and identity.user_id not in course.enrolled_users
        ):
            raise HTTPException(status_code=404, detail="Course not found")
        if not identity.is_admin and not course.has_instructor_access(identity.user_id):
            ensure_enrolled_or_owner(course.owner_id, course.enrolled_users, identity)
        if workspace_state_storage is not None:
            await workspace_state_storage.touch_course(identity.user_id, course_id)

        lessons = []
        for lesson_id, lesson_version in course.lessons.items():
            lesson = await artifact_storage.load_lesson(
                lesson_id, lesson_version, course_id=course_id
            )
            if lesson is not None:
                lessons.append(lesson)
        lesson_states = []
        if workspace_state_storage is not None:
            lesson_states = await workspace_state_storage.list_lesson_states(identity.user_id, course_id=course_id)
        ordered_lessons = order_lessons_for_user(course, lessons, lesson_states)
        pinned_window = resolve_pinned_lesson_window(course)
        return CourseLessonsResponse(
            lessons=[LessonSummaryResponse.from_lesson(lesson) for lesson in ordered_lessons],
            lesson_timeline=course.lesson_timeline,
            pinned_lesson_id=None if pinned_window is None else pinned_window.lesson_id,
            pinned_lesson_version=None if pinned_window is None else pinned_window.lesson_version,
        )

    @router.get("/{course_id}/lesson-timeline", response_model=CourseLessonTimelineResponse)
    async def get_lesson_timeline(
        course_id: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> CourseLessonTimelineResponse:
        """Return editable lesson timeline windows for an authorized instructor."""
        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_instructor(course, identity)

        pinned_window = resolve_pinned_lesson_window(course)
        return CourseLessonTimelineResponse(
            lesson_timeline=course.lesson_timeline,
            pinned_lesson_id=None if pinned_window is None else pinned_window.lesson_id,
            pinned_lesson_version=None if pinned_window is None else pinned_window.lesson_version,
        )

    @router.put("/{course_id}/lesson-timeline", response_model=CourseLessonTimelineResponse)
    async def update_lesson_timeline(
        course_id: str,
        payload: CourseLessonTimelineRequest,
        identity: UserIdentity = Depends(require_identity),
    ) -> CourseLessonTimelineResponse:
        """Replace lesson timeline windows for an authorized instructor."""
        course = await course_storage.get_course(course_id)
        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_instructor(course, identity)

        try:
            updated_course = Course.model_validate({
                **course.model_dump(),
                "lesson_timeline": [
                    window.model_dump()
                    for window in payload.lesson_timeline
                ],
            })
        except ValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            await course_storage.save_course(updated_course)
        except CourseRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        pinned_window = resolve_pinned_lesson_window(updated_course)
        return CourseLessonTimelineResponse(
            lesson_timeline=updated_course.lesson_timeline,
            pinned_lesson_id=None if pinned_window is None else pinned_window.lesson_id,
            pinned_lesson_version=None if pinned_window is None else pinned_window.lesson_version,
        )
        

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

        if course is None or course.archived_at is not None or not course.discoverable:
            raise HTTPException(status_code=404, detail="Course not found")

        if identity.user_id in course.enrolled_users:
            return {"status": "already_enrolled"}

        if identity.user_id not in course.pending_requests:
            course.pending_requests.append(identity.user_id)
            await save_course_or_409(course)

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

        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)

        return {"pending_requests": course.pending_requests}


    @router.post("/{course_id}/approve")
    async def approve_student(
        course_id: str,
        payload: UserTargetRequest,
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
        target_user = payload.user_id

        course = await course_storage.get_course(course_id)

        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)

        if target_user in course.pending_requests:
            course.pending_requests.remove(target_user)

            if target_user not in course.enrolled_users:
                course.enrolled_users.append(target_user)

            await save_course_or_409(course)

        return {"status": "approved"}


    @router.post("/{course_id}/remove")
    async def remove_student(
        course_id: str,
        payload: UserTargetRequest,
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
        target_user = payload.user_id

        course = await course_storage.get_course(course_id)

        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)

        if target_user in course.enrolled_users:
            course.enrolled_users.remove(target_user)
            await save_course_or_409(course)

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
        payload: UserTargetRequest,
        identity: UserIdentity = Depends(require_identity),
    ) -> CourseInstructorsResponse:
        """Add an authorized instructor to the course. Owner only."""
        target_user = payload.user_id
        course = await course_storage.get_course(course_id)
        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)
        if target_user not in course.instructor_ids:
            course.instructor_ids.append(target_user)
            await save_course_or_409(course)
        return CourseInstructorsResponse(owner_id=course.owner_id, instructor_ids=course.instructor_ids)

    @router.delete("/{course_id}/instructors/{user_id}", response_model=CourseInstructorsResponse)
    async def remove_instructor(
        course_id: str,
        user_id: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> CourseInstructorsResponse:
        """Remove an authorized instructor from the course. Owner only."""
        course = await course_storage.get_course(course_id)
        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_course_owner(course.owner_id, identity)
        if user_id == course.owner_id:
            raise HTTPException(status_code=400, detail="Owner cannot be removed from instructor list")
        if user_id in course.instructor_ids:
            course.instructor_ids.remove(user_id)
            await save_course_or_409(course)
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
            requester_is_admin=identity.is_admin,
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
        if not metadata.content_available:
            raise HTTPException(status_code=410, detail="Log content expired under the retention policy")
        payload = await encrypted_log_service.load_session_log_for_requester(
            session_id=session_id,
            requester_user_id=identity.user_id,
            requester_is_admin=identity.is_admin,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="Log not found")
        return payload

    @router.post("/{course_id}/lesson-artifacts")
    async def save_lesson_artifact(
        course_id: str,
        lesson: Lesson,
        expected_revision: int | None = None,
        identity: UserIdentity = Depends(require_identity),
    ) -> dict:
        """Create or overwrite a mutable lesson artifact for this course."""
        course = await course_storage.get_course(course_id)
        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_owner_or_admin(course, identity)
        existing = await artifact_storage.load_lesson(
            lesson.identity.lesson_id,
            lesson.identity.version,
            course_id=course_id,
        )
        if existing is not None and expected_revision is None:
            raise HTTPException(
                status_code=428,
                detail="Overwriting a lesson requires expected_revision from the latest read.",
            )
        try:
            revision = await artifact_storage.save_lesson(
                lesson,
                course_id=course_id,
                expected_revision=expected_revision,
            )
        except LessonRevisionConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": "ok",
            "lesson_id": lesson.identity.lesson_id,
            "version": lesson.identity.version,
            "artifact_revision": revision,
            "overwritten": existing is not None,
        }

    @router.get("/{course_id}/lesson-artifacts/{lesson_id}/{version}")
    async def get_lesson_artifact(
        course_id: str,
        lesson_id: str,
        version: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> dict:
        course = await course_storage.get_course(course_id)
        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_owner_or_admin(course, identity)
        lesson = await artifact_storage.load_lesson(lesson_id, version, course_id=course_id)
        if lesson is None:
            raise HTTPException(status_code=404, detail="Lesson not found")
        revision = await artifact_storage.get_lesson_revision(
            lesson_id,
            version,
            course_id=course_id,
        )
        return {"lesson": lesson, "artifact_revision": revision or 1}

    @router.post("/{course_id}/lessons")
    async def bind_course_lesson(
        course_id: str,
        request: LessonBindingRequest,
        identity: UserIdentity = Depends(require_identity),
    ) -> dict:
        course = await course_storage.get_course(course_id)
        if course is None or course.archived_at is not None:
            raise HTTPException(status_code=404, detail="Course not found")
        ensure_owner_or_admin(course, identity)
        lesson = await artifact_storage.load_lesson(
            request.lesson_id,
            request.version,
            course_id=course_id,
        )
        if lesson is None:
            raise HTTPException(status_code=404, detail="Lesson not found")
        course.lessons[request.lesson_id] = request.version
        course.lesson_timeline = [
            window
            for window in course.lesson_timeline
            if window.lesson_id != request.lesson_id
        ]
        await save_course_or_409(course)
        return {
            "status": "ok",
            "course_id": course_id,
            "lesson_id": request.lesson_id,
            "version": request.version,
        }

    return router
