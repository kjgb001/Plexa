from pydantic import BaseModel
from typing import List
from datetime import datetime
from plexa_server.models.session import Session
from plexa_server.models.message import Message
from plexa_server.models.lesson import Lesson
from plexa_server.models.session import SessionReflectionHook


class SessionResponse(BaseModel):
    """API projection of session state returned by session endpoints."""

    session_id: str
    title: str
    user_id: str
    course_id: str
    lesson_id: str
    lesson_version: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    turn_count: int
    max_turns: int
    is_completion_started: bool
    completed_at: datetime | None
    is_finalized: bool
    turned_in_at: datetime | None
    logging_policy: str
    reflection_hooks: List[SessionReflectionHook]

    @classmethod
    def from_session(cls, session: Session):
        """Build a response model from a persisted session object.

        Args:
            session: Session model to project into the API response shape.

        Returns:
            SessionResponse: Response model populated from the session.
        """
        return cls(
            session_id=session.session_id,
            title=session.title,
            user_id=session.user_id,
            course_id=session.course_id,
            lesson_id=session.lesson_id,
            lesson_version=session.lesson_version,
            created_at=session.created_at,
            updated_at=session.updated_at,
            is_active=session.is_active,
            turn_count=session.turn_count,
            max_turns=session.max_turns,
            is_completion_started=session.is_completion_started,
            completed_at=session.completed_at,
            is_finalized=session.is_finalized,
            turned_in_at=session.turned_in_at,
            logging_policy=session.logging_policy,
            reflection_hooks=session.reflection_hooks,
        )


class CourseLessonsResponse(BaseModel):
    """Response payload returned when listing lessons bound to a course."""

    lessons: List[Lesson]
    pinned_lesson_id: str | None = None
    pinned_lesson_version: str | None = None


class CourseInstructorsResponse(BaseModel):
    """Response payload returned when listing or mutating course instructors."""

    owner_id: str
    instructor_ids: List[str]


class EncryptedLogMetadataResponse(BaseModel):
    """API projection of plaintext encrypted-log metadata."""

    instance_id: str
    user_id: str
    course_id: str
    lesson_id: str
    lesson_version: str
    course_owner_id: str
    authorized_instructor_ids: List[str]
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    turn_count: int
    is_active: bool
    log_version: int
    artifact_sha256: str
    last_event_type: str
    last_event_at: datetime
    key_id: str


class EncryptedLogListResponse(BaseModel):
    """Response payload returned when listing course encrypted logs."""

    logs: List[EncryptedLogMetadataResponse]


class CreateSessionResponse(BaseModel):
    """Response payload for session creation and session fetch endpoints."""

    session: SessionResponse
    messages: List[Message]


class ListSessionsResponse(BaseModel):
    """Response payload for listing a learner's sessions for one lesson."""

    sessions: List[SessionResponse]


class DeleteSessionResponse(BaseModel):
    """Response payload returned after a session deletion succeeds."""

    status: str
    session_id: str


class SendMessageResponse(BaseModel):
    """Response payload returned after a successful user turn submission."""

    assistant_message: Message
    session: SessionResponse
