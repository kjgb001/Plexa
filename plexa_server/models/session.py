from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, UTC
from uuid import uuid4

from plexa_server.models.message import Message


class Session(BaseModel):
    """Persisted state for a user's lesson conversation."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "Untitled session"
    user_id: str

    lesson_id: str
    lesson_version: str
    course_id: str

    messages: List[Message] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    closed_at: Optional[datetime] = None

    turn_count: int = 0
    max_turns: Optional[int] = None

    is_active: bool = True
