from fastapi import APIRouter, HTTPException, Depends

from plexa_server.auth.user import require_user_id
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage
from plexa_server.api.schemas.responses import CourseLessonsResponse


def get_course_router(
    course_storage: CourseStorage, artifact_storage: ArtifactStorage
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
        user_id: str = Depends(require_user_id)
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
        user_id: str = Depends(require_user_id)
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
            or user_id == course.owner_id
            or user_id in course.enrolled_users
        ):
            return course

        raise HTTPException(status_code=404, detail="Course not found")


    @router.get("/{course_id}/lessons")
    async def get_course_lessons(
        course_id: str,
        user_id: str = Depends(require_user_id)
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

        if (
            course is None
            or not course.discoverable
            or user_id not in course.enrolled_users
            and user_id != course.owner_id
        ):
            raise HTTPException(status_code=404, detail="Course not found")
        
        else:
            lessons = []
            for lesson_id, lesson_version in course.lessons.items():
                lesson = await artifact_storage.load_lesson(lesson_id, lesson_version)
                if lesson is not None:
                    lessons.append(lesson)
            return CourseLessonsResponse(lessons=lessons)
        

    @router.post("/{course_id}/enroll")
    async def request_enrollment(
        course_id: str,
        user_id: str = Depends(require_user_id)
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

        if user_id in course.enrolled_users:
            return {"status": "already_enrolled"}

        if user_id not in course.pending_requests:
            course.pending_requests.append(user_id)
            await course_storage.save_course(course)

        return {"status": "pending"}


    @router.get("/{course_id}/requests")
    async def view_requests(
        course_id: str,
        user_id: str = Depends(require_user_id)
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

        if course is None or user_id != course.owner_id:
            raise HTTPException(status_code=404, detail="Course not found")

        return {"pending_requests": course.pending_requests}


    @router.post("/{course_id}/approve")
    async def approve_student(
        course_id: str,
        payload: dict,
        user_id: str = Depends(require_user_id)
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

        if (
            course is None
            or user_id != course.owner_id
            or target_user is None
        ):
            raise HTTPException(status_code=404, detail="Course not found")

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
        user_id: str = Depends(require_user_id)
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

        if (
            course is None
            or user_id != course.owner_id
            or target_user is None
        ):
            raise HTTPException(status_code=404, detail="Course not found")

        if target_user in course.enrolled_users:
            course.enrolled_users.remove(target_user)
            await course_storage.save_course(course)

        return {"status": "removed"}

    return router
