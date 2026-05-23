from fastapi import APIRouter, HTTPException, Depends, status
from uuid import uuid4

from plexa_server.core.sessions import (
    SessionClosedError,
    TurnLimitExceededError,
    SessionCompletionError,
)
from plexa_server.runtime import get_app_environment
from plexa_server.models.session import Session
from plexa_server.inference.base import InferenceError
from plexa_server.api.schemas.requests import SendMessageRequest, ReflectionResponseRequest

from plexa_server.api.schemas.responses import (
    SessionResponse,
    CreateSessionResponse,
    ListSessionsResponse,
    DeleteSessionResponse,
    SendMessageResponse,
)

from plexa_server.auth.dependencies import get_owned_session, require_identity
from plexa_server.auth.identity import UserIdentity
from plexa_server.core.sessions import SessionManager
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage, WorkspaceStateStorage


def get_sessions_router(
    session_manager: SessionManager,
    artifact_storage: ArtifactStorage,
    course_storage: CourseStorage,
    workspace_state_storage: WorkspaceStateStorage,
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

    async def touch_course_and_lesson(
        identity: UserIdentity,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
    ) -> None:
        """Record meaningful course and lesson access for sidebar ordering."""
        await workspace_state_storage.touch_course(identity.user_id, course_id)
        await workspace_state_storage.touch_lesson(
            identity.user_id,
            course_id,
            lesson_id,
            lesson_version,
        )


    async def load_lesson_or_404(lesson_id: str, lesson_version: str):
        lesson = await artifact_storage.load_lesson(
            lesson_id=lesson_id,
            version=lesson_version,
        )
        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )
        return lesson


    async def refresh_completion_reflections(session: Session) -> Session:
        """Ensure sessions already in completion mode have current reflection hooks."""
        if session.is_completion_started is False or session.is_finalized:
            return session

        lesson = await load_lesson_or_404(session.lesson_id, session.lesson_version)
        return await session_manager.begin_completion(session.session_id, current_lesson=lesson)


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
    async def create_session(
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity)
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
        lesson = await load_lesson_or_404(lesson_id, lesson_version)

        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )
        if identity.user_id not in course.enrolled_users and not course.has_instructor_access(identity.user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )

        session = await session_manager.create_session(
            lesson=lesson,
            user_id=identity.user_id,
            course_id=course_id
        )
        await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)

        return CreateSessionResponse(
            session=SessionResponse.from_session(session),
            messages=session.messages,
        )


    # List Sessions

    @router.get(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions",
        response_model=ListSessionsResponse,
    )
    async def list_sessions(
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity)
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
        lesson = await load_lesson_or_404(lesson_id, lesson_version)

        course = await course_storage.get_course(course_id)
        if course is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )
        if (
            identity.user_id not in course.enrolled_users
            and not course.has_instructor_access(identity.user_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found."
            )

        sessions = await session_manager.list_sessions(
            user_id=identity.user_id,
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
    async def send_message(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        request: SendMessageRequest,
        identity: UserIdentity = Depends(require_identity)
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
            session = await get_owned_session(session_manager, session_id, identity)
            check_session_path(session, course_id, lesson_id, lesson_version)
            lesson = await load_lesson_or_404(lesson_id, lesson_version)

            assistant_message = await session_manager.submit_user_message(
                session_id=session_id,
                message_id=message_id,
                content=request.content,
                current_lesson=lesson,
            )

            session = await session_manager.get_session(session_id)
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)

            return SendMessageResponse(
                assistant_message=assistant_message,
                session=SessionResponse.from_session(session),
            )

        except SessionClosedError:
            raise HTTPException(status_code=409, detail="Session is closed")

        except TurnLimitExceededError:
            raise HTTPException(status_code=409, detail="Turn limit exceeded")

        except SessionCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        except InferenceError as exc:
            detail = "Inference failure"
            if get_app_environment() != "production":
                detail = f"Inference failure: {exc}"
            raise HTTPException(status_code=502, detail=detail)


    # Get Session

    @router.get(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}",
        response_model=CreateSessionResponse,
    )
    async def get_session(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity)
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
            session = await get_owned_session(session_manager, session_id, identity)
            check_session_path(session, course_id, lesson_id, lesson_version)
            session = await refresh_completion_reflections(session)
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)

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
    async def close_session(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity)
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
            session = await get_owned_session(session_manager, session_id, identity)
            check_session_path(session, course_id, lesson_id, lesson_version)

            await session_manager.close_session(session_id)
            session = await session_manager.get_session(session_id)
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)
            return SessionResponse.from_session(session)

        except SessionClosedError:
            raise HTTPException(status_code=409, detail="Session already closed")


    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/complete",
        response_model=SessionResponse,
    )
    async def begin_completion(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> SessionResponse:
        session = await get_owned_session(session_manager, session_id, identity)
        check_session_path(session, course_id, lesson_id, lesson_version)

        try:
            lesson = await load_lesson_or_404(lesson_id, lesson_version)
            session = await session_manager.begin_completion(session_id, current_lesson=lesson)
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)
            return SessionResponse.from_session(session)
        except SessionCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))


    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/resume",
        response_model=SessionResponse,
    )
    async def resume_after_completion(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> SessionResponse:
        session = await get_owned_session(session_manager, session_id, identity)
        check_session_path(session, course_id, lesson_id, lesson_version)

        try:
            session = await session_manager.resume_after_completion(session_id)
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)
            return SessionResponse.from_session(session)
        except SessionCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))


    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/reflections/{hook_id}",
        response_model=SessionResponse,
    )
    async def save_reflection_response(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        hook_id: str,
        request: ReflectionResponseRequest,
        identity: UserIdentity = Depends(require_identity),
    ) -> SessionResponse:
        session = await get_owned_session(session_manager, session_id, identity)
        check_session_path(session, course_id, lesson_id, lesson_version)

        try:
            session = await session_manager.save_reflection_response(
                session_id,
                hook_id,
                request.response_text,
            )
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)
            return SessionResponse.from_session(session)
        except SessionCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))


    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/reflections/{hook_id}/postpone",
        response_model=SessionResponse,
    )
    async def postpone_reflection(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        hook_id: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> SessionResponse:
        session = await get_owned_session(session_manager, session_id, identity)
        check_session_path(session, course_id, lesson_id, lesson_version)

        try:
            session = await session_manager.postpone_reflection(session_id, hook_id)
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)
            return SessionResponse.from_session(session)
        except SessionCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))


    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/turn-in",
        response_model=SessionResponse,
    )
    async def turn_in_session(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity),
    ) -> SessionResponse:
        session = await get_owned_session(session_manager, session_id, identity)
        check_session_path(session, course_id, lesson_id, lesson_version)

        try:
            session = await refresh_completion_reflections(session)
            session = await session_manager.turn_in_session(session_id)
            await touch_course_and_lesson(identity, course_id, lesson_id, lesson_version)
            return SessionResponse.from_session(session)
        except SessionCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc))


    # Delete Session

    @router.post(
        "/courses/{course_id}/lessons/{lesson_id}/{lesson_version}/sessions/{session_id}/delete",
        response_model=DeleteSessionResponse,
    )
    async def delete_session(
        session_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
        identity: UserIdentity = Depends(require_identity)
    ) -> DeleteSessionResponse:
        """Delete an owned session and its persisted inference config.

        Args:
            session_id: Session identifier to delete.
            course_id: Course identifier from the route path.
            lesson_id: Lesson identifier from the route path.
            lesson_version: Lesson version from the route path.
            user_id: Caller identity resolved from the request header.

        Returns:
            DeleteSessionResponse: Deletion status payload.

        Raises:
            HTTPException: If the caller does not own the session or the
                session does not exist.
        """
        session = await get_owned_session(session_manager, session_id, identity)
        check_session_path(session, course_id, lesson_id, lesson_version)

        await session_manager.delete_session(session_id)

        return DeleteSessionResponse(
            status="deleted",
            session_id=session_id,
        )

    return router
