from pydantic import BaseModel
from typing import List

from plexa_server.models.course import CourseLessonWindow


class SendMessageRequest(BaseModel):
    """Request body for appending a user message to a session."""

    content: str
    message_id: str | None = None


class ReflectionResponseRequest(BaseModel):
    """Request body for saving a reflection response."""

    response_text: str


class CourseLessonTimelineRequest(BaseModel):
    """Request body for replacing a course lesson timeline."""

    lesson_timeline: List[CourseLessonWindow]
