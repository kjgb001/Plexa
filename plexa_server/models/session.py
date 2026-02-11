from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from plexa_server.models.message import Message


class Session(BaseModel):
    session_id: str
    user_id: str

    lesson_id: str
    lesson_version: str

    messages: List[Message] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

    turn_count: int = 0
    max_turns: Optional[int] = None

    is_active: bool = True
