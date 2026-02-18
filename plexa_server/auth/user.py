# Define UserIdentity, contains ID, role, and optional claims
from fastapi import Header, HTTPException

from plexa_server.core.sessions import SessionNotFoundError


def require_user_id(
    user_id: str | None = Header(default=None, alias="X-User-Id")
) -> str:
    if user_id is None:
        raise HTTPException(status_code=401, detail="Missing user identity")
    return user_id


def require_course_id(
    course_id: str | None = Header(default=None, alias="X-Course-Id")
) -> str:
    if course_id is None:
        raise HTTPException(status_code=401, detail="Missing course identity")
    return course_id


def get_owned_session(session_manager, session_id: str, user_id: str):
    '''Temporary simple header id check. Should fully implement proper auth flow later.'''
    try:
        session = session_manager.get_session(session_id)
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.user_id != user_id:
        # deliberate anti-enumeration
        raise HTTPException(status_code=404, detail="Session not found")

    return session