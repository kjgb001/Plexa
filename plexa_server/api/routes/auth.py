from fastapi import APIRouter, Depends

from plexa_server.api.schemas.responses import AuthMeResponse
from plexa_server.auth.dependencies import require_identity
from plexa_server.auth.identity import UserIdentity
from plexa_server.storage.storage_interface import CourseStorage


def get_auth_router(course_storage: CourseStorage) -> APIRouter:
    """Expose the server-authoritative identity used by both portal surfaces."""
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.get("/me", response_model=AuthMeResponse)
    async def get_me(
        identity: UserIdentity = Depends(require_identity),
    ) -> AuthMeResponse:
        courses = await course_storage.list_courses()
        owned = sorted(
            course.course_id
            for course in courses
            if course.owner_id == identity.user_id
        )
        instructed = sorted(
            course.course_id
            for course in courses
            if course.has_instructor_access(identity.user_id)
        )
        return AuthMeResponse(
            user_id=identity.user_id or "",
            roles=sorted(identity.roles),
            is_admin=identity.is_admin,
            can_access_instructor_portal=identity.is_admin or bool(instructed),
            owned_course_ids=owned,
            instructed_course_ids=instructed,
        )

    return router
