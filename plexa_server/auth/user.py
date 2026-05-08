# Define UserIdentity, contains ID, role, and optional claims
from fastapi import Header, HTTPException

from plexa_server.core.sessions import SessionNotFoundError


def require_user_id(
    user_id: str | None = Header(default=None, alias="X-User-Id")
) -> str:
    """Require the caller to supply a user identifier header.

    Args:
        user_id: User identifier supplied through the `X-User-Id` header.

    Returns:
        str: Caller user identifier.

    Raises:
        HTTPException: If the caller does not supply a user id header.
    """
    if user_id is None:
        raise HTTPException(status_code=401, detail="Missing user identity")
    return user_id


def require_course_id(
    course_id: str | None = Header(default=None, alias="X-Course-Id")
) -> str:
    """Require the caller to supply a course identifier header.

    Args:
        course_id: Course identifier supplied through the `X-Course-Id`
            header.

    Returns:
        str: Caller course identifier.

    Raises:
        HTTPException: If the caller does not supply a course id header.
    """
    if course_id is None:
        raise HTTPException(status_code=401, detail="Missing course identity")
    return course_id
    

async def get_owned_session(session_manager, session_id: str, user_id: str):
    """Return a session only when it exists and belongs to the caller.

    Args:
        session_manager: Session manager used to load the session.
        session_id: Identifier of the session to load.
        user_id: Identifier of the caller who must own the session.

    Returns:
        Session: Session belonging to the caller.

    Raises:
        HTTPException: If the session does not exist or is owned by another
            user.
    """
    try:
        session = await session_manager.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != user_id:
        # deliberate anti-enumeration
        raise HTTPException(status_code=404, detail="Session not found")

    return session
