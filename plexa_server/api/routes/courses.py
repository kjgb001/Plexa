from fastapi import APIRouter, Header, HTTPException, Depends, status
from fastapi.responses import JSONResponse

from plexa_server.auth.user import require_user_id


def get_course_router(
    course_storage: FileSystemCourseStorage, artifact_storage: FileSystemArtifactStorage
) -> APIRouter:

    router = APIRouter(prefix="/courses", tags=["courses"])

    @router.get("")
    def list_discoverable_courses(
        user_id: str = Depends(require_user_id)
    ):
        courses = course_storage.list_courses()

        visible = [
            c for c in courses
            if c.discoverable
        ]

        return {"courses": visible}

    @router.get("/{course_id}")
    def get_course(
        course_id: str,
        user_id: str = Depends(require_user_id)
    ):
        course = course_storage.get_course(course_id)

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
    def get_course_lessons(
        course_id: str,
        user_id: str = Depends(require_user_id)
    ):
        course = course_storage.get_course(course_id)

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
                lessons.append(artifact_storage.load_lesson(lesson_id, lesson_version))
            return lessons
        

    @router.post("/{course_id}/enroll")
    def request_enrollment(
        course_id: str,
        user_id: str = Depends(require_user_id)
    ):
        course = course_storage.get_course(course_id)

        if course is None or not course.discoverable:
            raise HTTPException(status_code=404, detail="Course not found")

        if user_id in course.enrolled_users:
            return {"status": "already_enrolled"}

        if user_id not in course.pending_requests:
            course.pending_requests.append(user_id)
            course_storage.save_course(course)

        return {"status": "pending"}


    @router.get("/{course_id}/requests")
    def view_requests(
        course_id: str,
        user_id: str = Depends(require_user_id)
    ):
        course = course_storage.get_course(course_id)

        if course is None or user_id != course.owner_id:
            raise HTTPException(status_code=404, detail="Course not found")

        return {"pending_requests": course.pending_requests}


    @router.post("/{course_id}/approve")
    def approve_student(
        course_id: str,
        payload: dict,
        user_id: str = Depends(require_user_id)
    ):
        target_user = payload.get("user_id")

        course = course_storage.get_course(course_id)

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

            course_storage.save_course(course)

        return {"status": "approved"}


    @router.post("/{course_id}/remove")
    def remove_student(
        course_id: str,
        payload: dict,
        user_id: str = Depends(require_user_id)
    ):
        target_user = payload.get("user_id")

        course = course_storage.get_course(course_id)

        if (
            course is None
            or user_id != course.owner_id
            or target_user is None
        ):
            raise HTTPException(status_code=404, detail="Course not found")

        if target_user in course.enrolled_users:
            course.enrolled_users.remove(target_user)
            course_storage.save_course(course)

        return {"status": "removed"}

    return router
