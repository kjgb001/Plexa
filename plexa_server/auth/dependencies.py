from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, Request

from plexa_server.auth.identity import UserIdentity
from plexa_server.core.sessions import SessionNotFoundError
from plexa_server.models.course import Course


def get_request_identity(request: Request) -> UserIdentity:
    """Return the request identity previously attached by middleware.

    Args:
        request: Incoming FastAPI request.

    Returns:
        UserIdentity: Resolved request identity.
    """
    identity = getattr(request.state, "identity", None)
    if isinstance(identity, UserIdentity):
        return identity
    return UserIdentity()


def require_identity(request: Request) -> UserIdentity:
    """Require a caller identity for user-scoped routes.

    Args:
        request: Incoming FastAPI request.

    Returns:
        UserIdentity: Authenticated request identity.

    Raises:
        HTTPException: If the request is anonymous.
    """
    identity = get_request_identity(request)
    if not identity.is_authenticated:
        if identity.claims.get("bearer_token_present") and not identity.claims.get("bearer_token_valid", True):
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        raise HTTPException(status_code=401, detail="Missing user identity")
    return identity


def require_user_id(request: Request) -> str:
    """Return the authenticated caller's user id.

    This is a compatibility helper for code that still expects the older
    string-returning dependency shape.

    Args:
        request: Incoming FastAPI request.

    Returns:
        str: Authenticated caller user id.
    """
    return require_identity(request).user_id  # type: ignore[return-value]


def require_admin(request: Request) -> UserIdentity:
    """Require an administrative identity for admin-only routes.

    Args:
        request: Incoming FastAPI request.

    Returns:
        UserIdentity: Identity carrying the admin role.

    Raises:
        HTTPException: If the caller is not a Plexa admin.
    """
    identity = get_request_identity(request)
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail="Admin access denied")
    return identity


def require_admin_token(request: Request) -> str:
    """Return a validated admin compatibility sentinel.

    This is a compatibility helper for code that still expects the older
    string-returning dependency shape.

    Args:
        request: Incoming FastAPI request.

    Returns:
        str: Stable compatibility sentinel for validated admin access.
    """
    require_admin(request)
    return "validated-admin-identity"


def ensure_course_owner(course_owner_id: str, identity: UserIdentity) -> None:
    """Require that the caller owns the referenced course.

    Args:
        course_owner_id: Owning course user id.
        identity: Caller identity.

    Raises:
        HTTPException: If the caller is not the course owner.
    """
    if identity.user_id != course_owner_id:
        raise HTTPException(status_code=404, detail="Course not found")


def ensure_course_instructor(course: Course, identity: UserIdentity) -> None:
    """Require that the caller is an authorized instructor for the course."""
    if not course.has_instructor_access(identity.user_id):
        raise HTTPException(status_code=404, detail="Course not found")


def ensure_enrolled_or_owner(
    course_owner_id: str,
    enrolled_users: Iterable[str],
    identity: UserIdentity,
) -> None:
    """Require that the caller is enrolled in or owns the referenced course.

    Args:
        course_owner_id: Owning course user id.
        enrolled_users: Enrolled course user ids.
        identity: Caller identity.

    Raises:
        HTTPException: If the caller is neither enrolled nor the owner.
    """
    user_id = identity.user_id
    if user_id is None or (user_id != course_owner_id and user_id not in set(enrolled_users)):
        raise HTTPException(status_code=404, detail="Course not found")


async def get_owned_session(session_manager, session_id: str, identity: UserIdentity):
    """Return a session only when it exists and belongs to the caller.

    Args:
        session_manager: Session manager used to load the session.
        session_id: Identifier of the session to load.
        identity: Caller identity that must own the session.

    Returns:
        Session: Session belonging to the caller.

    Raises:
        HTTPException: If the session does not exist or belongs to another user.
    """
    try:
        session = await session_manager.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != identity.user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    return session
