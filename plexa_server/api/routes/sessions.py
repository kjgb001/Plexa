from fastapi import APIRouter, HTTPException, status
from uuid import uuid4

from plexa_server.core.sessions import (
    SessionNotFoundError,
    SessionClosedError,
    TurnLimitExceededError
)
from plexa_server.inference.base import InferenceError
from plexa_server.api.schemas.requests import (
    CreateSessionRequest,
    SendMessageRequest,
)
from plexa_server.api.schemas.responses import (
    SessionResponse,
    CreateSessionResponse,
    SendMessageResponse,
)

from plexa_server.core.sessions import SessionManager
from plexa_server.storage.filesystem import FileSystemArtifactStorage


def get_sessions_router(
    session_manager: SessionManager,
    artifact_storage: FileSystemArtifactStorage,
) -> APIRouter:

    router = APIRouter(prefix="/sessions", tags=["sessions"])

    # Create Session

    @router.post(
        "",
        response_model=CreateSessionResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_session(request: CreateSessionRequest):
        lesson = artifact_storage.load_lesson(
            lesson_id=request.lesson_id,
            version=request.lesson_version,
        )

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        session = session_manager.create_session(
            lesson=lesson,
            user_id=request.user_id,
        )

        return CreateSessionResponse(
            session=SessionResponse.from_session(session),
            messages=session.messages,
        )


    # Send Message

    @router.post(
        "/{session_id}/messages",
        response_model=SendMessageResponse,
    )
    def send_message(session_id: str, request: SendMessageRequest):
        message_id = request.message_id or str(uuid4())

        try:
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

        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")

        except SessionClosedError:
            raise HTTPException(status_code=409, detail="Session is closed")

        except TurnLimitExceededError:
            raise HTTPException(status_code=409, detail="Turn limit exceeded")

        except InferenceError:
            raise HTTPException(status_code=502, detail="Inference failure")


    # Get Session

    @router.get(
        "/{session_id}",
        response_model=CreateSessionResponse,
    )
    def get_session(session_id: str):
        try:
            session = session_manager.get_session(session_id)

            return CreateSessionResponse(
                session=SessionResponse.from_session(session),
                messages=session.messages,
            )

        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")


    # Close Session

    @router.post(
        "/{session_id}/close",
        response_model=SessionResponse,
    )
    def close_session(session_id: str):
        try:
            session_manager.close_session(session_id)
            session = session_manager.get_session(session_id)
            return SessionResponse.from_session(session)

        except SessionNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")

        except SessionClosedError:
            raise HTTPException(status_code=409, detail="Session already closed")

    return router
