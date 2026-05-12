from datetime import UTC, datetime

from pydantic import BaseModel, Field


class UserCourseState(BaseModel):
    """User-scoped recency state for a course in the sidebar workspace."""

    user_id: str
    course_id: str
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class UserLessonState(BaseModel):
    """User-scoped recency state for a lesson in the sidebar workspace."""

    user_id: str
    course_id: str
    lesson_id: str
    lesson_version: str
    last_accessed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
