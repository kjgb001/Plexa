from pydantic import BaseModel, ConfigDict, Field
from typing import List

from plexa_server.models.course import CourseLessonWindow


class SendMessageRequest(BaseModel):
    """Request body for appending a user message to a session."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=16_000)
    message_id: str | None = Field(default=None, min_length=1, max_length=255)


class ReflectionResponseRequest(BaseModel):
    """Request body for saving a reflection response."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    response_text: str = Field(min_length=1, max_length=16_000)


class CourseLessonTimelineRequest(BaseModel):
    """Request body for replacing a course lesson timeline."""

    model_config = ConfigDict(extra="forbid")

    lesson_timeline: List[CourseLessonWindow]


class UserTargetRequest(BaseModel):
    """Strict request selecting one external user id."""

    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=255)


class LessonBindingRequest(BaseModel):
    """Strict request binding one course-owned lesson artifact."""

    model_config = ConfigDict(extra="forbid")
    lesson_id: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)
