from pydantic import BaseModel
from typing import List
from datetime import datetime
from plexa_server.models.session import Session
from plexa_server.models.message import Message


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    lesson_id: str
    lesson_version: str
    created_at: datetime
    is_active: bool
    turn_count: int
    max_turns: int

    @classmethod
    def from_session(cls, session: Session):
        return cls(
            session_id=session.session_id,
            user_id=session.user_id,
            lesson_id=session.lesson_id,
            lesson_version=session.lesson_version,
            created_at=session.created_at,
            is_active=session.is_active,
            turn_count=session.turn_count,
            max_turns=session.max_turns,
        )


class CreateSessionResponse(BaseModel):
    session: SessionResponse
    messages: List[Message]


class SendMessageResponse(BaseModel):
    assistant_message: Message
    session: SessionResponse
