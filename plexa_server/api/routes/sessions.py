from fastapi import APIRouter, HTTPException, Depends, status
from uuid import uuid4

from plexa_server.core.sessions import (
    SessionClosedError,
    TurnLimitExceededError
)
from plexa_server.models.session import Session
from plexa_server.inference.base import InferenceError
from plexa_server.api.schemas.requests import SendMessageRequest

from plexa_server.api.schemas.responses import (
    SessionResponse,
    CreateSessionResponse,
    ListSessionsResponse,
    SendMessageResponse,
)

from plexa_server.auth.user import require_user_id, get_owned_session
from plexa_server.core.sessions import SessionManager
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage


def get_sessions_router(
    session_manager: SessionManager,
    artifact_storage: ArtifactStorage,
    course_storage: CourseStorage
) -> APIRouter:
    """Create session endpoints bound to the supplied storage and manager objects.

    Args:
        session_manager: Session manager handling lifecycle mutations.
        artifact_storage: Artifact storage used to load lesson definitions.
        course_storage: Course storage used for enrollment checks.

    Returns:
        APIRouter: Router exposing session lifecycle endpoints.
    """

    router = APIRouter(tags=["sessions"])


    def check_session_path(
        session: Session, 
        course_id: str, 
        lesson_id: str,
        lesson_version: str
    ) -> None:
        """Check api path variables against session attributes.
        
        Args:
            session: Session object to test against.
            course_id: Course identifier specified in path.
            lesson_id: Lesson identifier specified in path.
            lesson_version: Lesson version identifier specified in path.

        Raises:
            HTTPException: If any identifiers do not match session attributes.
        """
        if (session.course_id == course_id and
            session.lesson_id == lesson_id and
            session.lesson_version == lesson_version):
            return

        raise HTTPException(status_code=404, detail="Session not found.")
        

    # Create Session

    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        response_model=CreateSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_session(
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        user_id: str = Depends(require_user_id)
    ) -> CreateSessionResponse:
        """Create a new lesson session for an enrolled user.

        Args:
            course_id: Course containing the requested lesson.
            lesson_id: Lesson identifier to load.
            lesson_version: Lesson version to load.
            user_id: Caller identity resolved from the request header.

        Returns:
            CreateSessionResponse: Session summary and initial transcript.

        Raises:
            HTTPException: If the lesson does not exist, the course does not
                exist, or the caller is not allowed to create a session.
        """
        lesson = artifact_storage.load_lesson(
            lesson_id=lesson_id,
            version=lesson_version,
        )

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        course = course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )
        if user_id not in course.enrolled_users and user_id != course.owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )

        session = session_manager.create_session(
            lesson=lesson,
            user_id=user_id,
            course_id=course_id
        )

        return CreateSessionResponse(
            session=SessionResponse.from_session(session),
            messages=session.messages,
        )


    # List Sessions

    @router.get(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        response_model=ListSessionsResponse,
    )
    def list_sessions(
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        user_id: str = Depends(require_user_id)
    ) -> ListSessionsResponse:
        """Return the caller's sessions for a specific course lesson version.

        Args:
            course_id: Course containing the requested lesson.
            lesson_id: Lesson identifier to match.
            lesson_version: Lesson version to match.
            user_id: Caller identity resolved from the request header.

        Returns:
            ListSessionsResponse: Matching session summaries ordered newest first.

        Raises:
            HTTPException: If the lesson does not exist, the course does not
                exist, or the caller is not allowed to view sessions for it.
        """
        lesson = artifact_storage.load_lesson(
            lesson_id=lesson_id,
            version=lesson_version,
        )

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        course = course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )
        if user_id not in course.enrolled_users and user_id != course.owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )

        sessions = session_manager.list_sessions(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            lesson_version=lesson_version,
        )

        return ListSessionsResponse(
            sessions=[SessionResponse.from_session(session) for session in sessions]
        )


    # Send Message

    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/messages",
        response_model=SendMessageResponse,
    )
    def send_message(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        request: SendMessageRequest,
        user_id: str = Depends(require_user_id)
    ) -> SendMessageResponse:
        """Append a user message to a session and return the assistant reply.

        Args:
            session_id: Session identifier to mutate.
            course_id: Course identifier from the route path.
            request: Request payload containing message content and id.
            user_id: Caller identity resolved from the request header.

        Returns:
            SendMessageResponse: Assistant reply and updated session summary.

        Raises:
            HTTPException: If the session is closed, the turn limit is exceeded,
                inference fails, or the caller does not own the session.
        """
        message_id = request.message_id or str(uuid4())

        try:
            session = get_owned_session(session_manager, session_id, user_id)
            check_session_path(session, course_id, lesson_id, lesson_version)

            assistant_message = session_manager.submit_user_message(
                session_id=session_id,
                message_id=message_id,
                content=request.content,
            )

            session = session_manager.get_session(session_id)

            return SendMessageResponse(
                assistant_message=assistant_message,
                session=SessionResponse.from_session(session),
            )

        except SessionClosedError:
            raise HTTPException(status_code=409, detail="Session is closed")

        except TurnLimitExceededError:
            raise HTTPException(status_code=409, detail="Turn limit exceeded")

        except InferenceError:
            raise HTTPException(status_code=502, detail="Inference failure")


    # Get Session

    @router.get(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}",
        response_model=CreateSessionResponse,
    )
    def get_session(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        user_id: str = Depends(require_user_id)
    ) -> CreateSessionResponse:
        """Return the full transcript for a session owned by the caller.

        Args:
            session_id: Session identifier to load.
            course_id: Course identifier from the route path.
            user_id: Caller identity resolved from the request header.

        Returns:
            CreateSessionResponse: Session summary and full transcript.

        Raises:
            HTTPException: If the caller does not own the session or the
                session does not exist.
        """
        try:
            session = get_owned_session(session_manager, session_id, user_id)
            check_session_path(session, course_id, lesson_id, lesson_version)

            return CreateSessionResponse(
                session=SessionResponse.from_session(session),
                messages=session.messages,
            )
        
        finally:
            pass


    # Close Session

    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/close",
        response_model=SessionResponse,
    )
    def close_session(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        user_id: str = Depends(require_user_id)
    ) -> SessionResponse:
        """Close an owned session and return its updated summary.

        Args:
            session_id: Session identifier to close.
            course_id: Course identifier from the route path.
            lesson_id: Lesson identifier from the route path.
            lesson_version: Lesson version from the route path.
            user_id: Caller identity resolved from the request header.

        Returns:
            SessionResponse: Updated session summary after closure.

        Raises:
            HTTPException: If the caller does not own the session or the
                session is already closed.
        """
        try:
            session = get_owned_session(session_manager, session_id, user_id)
            check_session_path(session, course_id, lesson_id, lesson_version)

            session_manager.close_session(session_id)
            session = session_manager.get_session(session_id)
            return SessionResponse.from_session(session)

        except SessionClosedError:
            raise HTTPException(status_code=409, detail="Session already closed")

    return router
